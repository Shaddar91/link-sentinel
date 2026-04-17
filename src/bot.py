"""Telegram bot for monitoring GitHub and YouTube links."""
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import structlog
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from .config import Settings, get_settings
from .github_parser import extract_github_urls, GitHubRepo
from .youtube_parser import extract_youtube_urls, YouTubeVideo
from .task_generator import create_repo_analysis_task, write_task_file
from .result_watcher import track_task, check_results
from .pdf_generator import markdown_to_pdf
from .video_processor import process_video

log = structlog.get_logger()

REPO_PROMPT = (
    "Analyze this repository. Cover the following:\n\n"
    "1. What does it do? (plain language, one paragraph)\n"
    "2. What language/framework is it written in?\n"
    "3. How does it work? Architecture, main components, data flow.\n"
    "4. Is it dockerized? docker-compose? How many services?\n"
    "5. How hard is it to get running? Prerequisites, steps, env vars, gotchas.\n"
    "6. What problem does it solve and who is it for?\n"
    "7. Name 2-3 similar/competing tools and how this compares — be opinionated.\n"
    "8. Is it actively maintained? How mature?\n"
    "9. Any red flags, security concerns, or deal-breakers?\n\n"
    "Do NOT list the folder structure or file tree. "
    "Focus on what matters for deciding whether to use it."
)

DETAILED_REPO_PROMPT = (
    "Produce an IN-DEPTH, NARRATIVE analysis of this repository — a report a busy engineer "
    "could read INSTEAD of cloning and spelunking for an hour. Go beyond a checklist: read "
    "the actual source (not just README/docs), cite concrete file paths and line numbers "
    "for every non-trivial claim, and write in flowing prose. Bullets are only allowed "
    "inside lists (dependencies, competing tools, red flags). Use WebSearch to verify "
    "library versions, CVE references, maintainer reputations, and competitive claims; use "
    "WebFetch to confirm documentation links and upstream repos. If you can't verify "
    "something, mark it 'unverified' rather than guessing.\n\n"
    "Follow this 13-section scaffold. Each section is a multi-paragraph narrative.\n\n"
    "1. **Executive overview (2-3 paragraphs).** What the repo does in plain language, who "
    "it's aimed at, the problem it solves, the stakes for a team adopting it, and the "
    "one-sentence elevator pitch. End with a 'why this matters right now' paragraph that "
    "situates it against the current tooling landscape.\n"
    "2. **Architecture deep-dive (prose with diagram).** Walk through the components as a "
    "story: what kicks off a request, where state lives, who calls whom, and how data "
    "flows end-to-end. Include a mermaid diagram when it genuinely clarifies flow. For "
    "each major component, write a paragraph citing the exact file (e.g. `src/foo.py:120`) "
    "and explain its responsibility, its collaborators, and the failure modes it guards "
    "against.\n"
    "3. **Tech stack breakdown (paragraph per choice).** For every language, framework, "
    "and notable library, write a mini-paragraph: what it is, why this project chose it "
    "over alternatives, what it costs (license, runtime overhead, learning curve), and a "
    "canonical WebSearch-verified reference link. Note the actual versions pinned in the "
    "lockfile.\n"
    "4. **Code quality assessment (evidence-based prose).** Move section by section "
    "through the code and describe patterns/anti-patterns with *quoted snippets* and line "
    "references. Discuss modularity, naming, test coverage, error handling, and "
    "readability. If a function is a mess, quote the worst 6-10 lines and explain why. If "
    "something is elegant, quote it and explain why.\n"
    "5. **Dependency analysis (paragraph + risk table).** Talk through the dependency "
    "graph: direct deps, transitive risk, abandonware, outdated majors, license "
    "incompatibilities. Cross-check CVE databases via WebSearch for anything pinned below "
    "a known-fixed version. Do not fabricate CVE numbers — only cite what you can verify.\n"
    "6. **Build, deploy, and reproducibility story (narrative).** Walk through what "
    "happens from `git clone` to a running service. Docker? compose? native? What env "
    "vars, secrets, volumes, ports? How reproducible is a clean build on a fresh machine? "
    "Cite the exact `Dockerfile`, compose file, and scripts. Call out anything the README "
    "implies but doesn't spell out.\n"
    "7. **Runtime behaviour (prose).** How does it behave under load, on failure, on "
    "partial data? Error handling strategy, observability (logging, metrics, traces), "
    "concurrency model, known scalability walls. Cite the specific handlers and any "
    "retry/backoff code.\n"
    "8. **Security review (prose, cited).** Authn/authz flow, input validation, secret "
    "management, attack surface, and notable hardening choices. Walk through the trust "
    "boundaries in paragraph form, citing the files where each boundary is enforced. "
    "WebSearch for known issues in the dependencies; cite only verifiable advisories.\n"
    "9. **Extensibility (narrative).** A paragraph per extension point (plugins, hooks, "
    "adapters, config knobs). What's the contract? What breaks if you push on it? How "
    "would you add Feature X — walk through the concrete steps and files you'd touch.\n"
    "10. **Competitive landscape (paragraph per competitor).** Pick 3-5 serious "
    "alternatives — verify each one exists via WebSearch, link to its repo/docs — and "
    "write a paragraph comparing functionality, maturity, license, community size, and "
    "fit. End with an opinionated pick: for *this* use case, which one wins and why.\n"
    "11. **Maintenance health (prose).** Commit cadence, open/closed issue ratio, PR "
    "responsiveness, bus factor, ownership/funding model, release rhythm. Quote a couple "
    "of recent issues or PRs that reveal how the maintainers actually respond. Use "
    "WebSearch or WebFetch to pull live GitHub data where useful.\n"
    "12. **Red flags and deal-breakers (list with paragraphs).** Enumerate them as a "
    "numbered list, but each item is a 3-5 sentence paragraph explaining the risk, the "
    "evidence, and how bad it really is. No vague 'code quality issues' hand-waving.\n"
    "13. **Adoption recommendation (editorial verdict, 2-3 paragraphs).** Be blunt. Who "
    "should adopt this, under what conditions, and what they're signing up for. Who "
    "should NOT and why. If it's a 'no' for production but a 'yes' for prototyping, say "
    "so in exactly those terms.\n\n"
    "Do NOT list the folder structure or file tree. Every claim about behavior or quality "
    "cites a file path. Every competitive claim is WebSearch-verified. Preserve technical "
    "accuracy over brevity; aim for a report an expert reader could rely on without "
    "double-checking the repo themselves. When uncertain, say 'unverified' — do not "
    "fabricate version numbers, CVE IDs, or maintainer claims."
)

VIDEO_PROMPT = (
    "Summarize this video:\n\n"
    "1. What is the video about? (one paragraph)\n"
    "2. Key points and main takeaways.\n"
    "3. Any technical details or explanations worth noting.\n"
    "4. Actionable steps or practical advice mentioned.\n"
    "5. Who is this useful for?\n\n"
    "Be concise and structured."
)

DETAILED_VIDEO_PROMPT = (
    "Produce an IN-DEPTH, NARRATIVE breakdown of this video — a report a busy expert "
    "could read INSTEAD of watching the full talk. Write in flowing prose inside each "
    "section; bullets are only allowed inside explicit lists (resources, playbook steps, "
    "concept glossary, red flags). Extract everything a viewer would want to reference "
    "later: direct quotes where the wording matters, verbatim code/commands, and "
    "fact-checked claims. Use WebSearch aggressively to verify the speaker's credentials, "
    "material claims, cited papers, version numbers, and library behavior before "
    "repeating them. Use WebFetch to confirm any linked resource still resolves and "
    "actually says what the speaker implies. If you cannot verify a claim, mark it "
    "'unverified' rather than restating it as fact.\n\n"
    "Follow this 12-section scaffold. Each section is multi-paragraph prose unless noted.\n\n"
    "1. **Executive overview (2-3 paragraphs).** What the video is about, why someone "
    "would watch it, what the stakes are for the target audience, and where it sits "
    "against the broader conversation on this topic. Not a one-liner — paint the context "
    "so a stranger knows whether this is relevant to them.\n"
    "2. **Speaker / presenter deep profile (paragraphs, WebSearch-verified).** Who they "
    "are, their track record, the institution or company they represent, their framing "
    "and worldview, known biases or commercial interests, and why they have standing to "
    "speak on this topic. If you don't already know them, WebSearch their name + the "
    "topic to confirm credentials and cite canonical sources. Flag any conflicts of "
    "interest (vendor talk, paid promotion, evangelism for their own tool).\n"
    "3. **Narrative section-by-section walkthrough (paragraph per section, with "
    "timestamps).** For each major section of the talk, write a full paragraph that "
    "re-tells what happened: the speaker's line of reasoning, the examples they used, at "
    "least one **direct quote** where the exact wording carries weight, and a closing "
    "sentence on how this section advances the overall argument. Include the timestamp "
    "or marker at the start of each section heading.\n"
    "4. **Concept glossary (mini-paragraph per term).** Every technical term, tool, "
    "framework, paper, library, or proper noun mentioned gets 3-6 sentences: what it is, "
    "why it matters in this context, how it relates to adjacent ideas, and — if the "
    "audience might not know it — a WebSearch-verified link to a canonical reference. "
    "Do NOT reduce this to one-line definitions.\n"
    "5. **Verbatim artifacts (reproduced exactly, with surrounding prose).** Code "
    "snippets, commands, config values, architectural diagrams — quote them verbatim in "
    "fenced blocks and wrap each one with a paragraph explaining what it does, when "
    "you'd use it, what the failure mode looks like, and any caveats the speaker glossed "
    "over.\n"
    "6. **Claim ledger (mini-paragraph per material claim).** For every non-trivial "
    "claim: restate the claim, summarise the speaker's evidence, note counter-evidence "
    "you found via WebSearch if any, and label it 'verified / unverified / disputed'. "
    "Be explicit about fabrication risk for numbers, benchmarks, percentages, and 'X "
    "times faster' style claims — verify them or mark them unverified. Do not launder "
    "unsupported claims into fact.\n"
    "7. **Counterpoints and missing perspectives (prose).** Not only what the speaker "
    "conceded, but what they DIDN'T address. Who in the field would push back, on what "
    "grounds, and with what evidence? Which use cases, constraints, or populations does "
    "this advice fail for? Write this as a fair-minded adversarial review.\n"
    "8. **Implications and applications (prose with examples).** How do these ideas "
    "generalise beyond the speaker's immediate use case? Where do they break down? Give "
    "concrete examples of applying the ideas in 2-3 adjacent domains, and name the "
    "conditions under which you'd NOT apply them.\n"
    "9. **Actionable playbook (numbered list, 1-2 sentences per step).** Ordered steps "
    "a viewer should take to put the ideas into practice. Each step is a sentence or two "
    "with enough specificity to be actionable — not a one-word todo. Include "
    "prerequisites, expected effort, and a 'how you'll know it worked' cue.\n"
    "10. **Resource index (one-paragraph annotation per item).** Every mentioned paper, "
    "repo, blog post, book, tool, dataset, or person to follow. For each item write a "
    "paragraph on why it's worth the reader's time and who it's aimed at. Confirm each "
    "link still resolves via WebFetch; drop or flag dead links.\n"
    "11. **Audience fit (two paragraphs).** One paragraph on who should watch this and "
    "at what level of background they'll get value. One paragraph on who should skip "
    "and why it'd waste their time (too basic, too narrow, too vendor-pitchy, already "
    "superseded, etc.).\n"
    "12. **Opinionated verdict (2-3 paragraphs, editorial).** Is this worth the time? "
    "What's the best 15-minute segment — timestamps please. What would you cut, what "
    "would you have pushed back on, what's the real takeaway vs. the marketing "
    "takeaway? Be blunt. Land on a clear recommendation.\n\n"
    "Preserve technical accuracy over brevity. Write in flowing prose inside each "
    "section; bullets are only allowed inside the explicit lists above. When uncertain "
    "about a speaker claim, verify with WebSearch before repeating it — and if you "
    "can't verify, label it 'unverified'. Do not fabricate credentials, benchmarks, "
    "CVE IDs, paper titles, or library version behavior. Aim for a report a busy "
    "expert could read instead of watching the video."
)

ANALYSIS_DEPTHS = ("standard", "detailed")


class LinkSentinelBot:
    """Telegram bot that monitors channels for GitHub and YouTube links."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.application: Application = None
        #Pending links waiting for delivery format choice — persisted to disk so restarts don't wipe state
        self._pending_path = Path(__file__).parent.parent / "data" / "state" / "pending.json"
        self._pending: dict[str, dict] = self._load_pending()

    def _load_pending(self) -> dict[str, dict]:
        """Load pending state from disk, reconstructing dataclasses."""
        try:
            if not self._pending_path.exists():
                return {}
            raw = json.loads(self._pending_path.read_text())
            restored: dict[str, dict] = {}
            for key, entry in raw.items():
                if entry.get("type") == "repo" and isinstance(entry.get("repo"), dict):
                    entry["repo"] = GitHubRepo(**entry["repo"])
                #Video entries stay as plain dicts — YouTubeVideo is built at dispatch time.
                restored[key] = entry
            log.info("pending_loaded", count=len(restored))
            return restored
        except Exception as e:
            log.warning("pending_load_failed", error=str(e))
            return {}

    def _save_pending(self) -> None:
        """Persist pending state to disk atomically."""
        try:
            self._pending_path.parent.mkdir(parents=True, exist_ok=True)
            serializable: dict[str, dict] = {}
            for key, entry in self._pending.items():
                copy = dict(entry)
                if copy.get("type") == "repo" and not isinstance(copy.get("repo"), dict):
                    copy["repo"] = asdict(copy["repo"])
                serializable[key] = copy
            tmp = self._pending_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(serializable, indent=2))
            tmp.replace(self._pending_path)
        except Exception as e:
            log.error("pending_save_failed", error=str(e))

    def _is_allowed(self, update: Update) -> bool:
        """Check if the message comes from an allowed chat."""
        chat = update.effective_chat
        chat_id = chat.id if chat else None
        user_id = update.effective_user.id if update.effective_user else None

        if user_id == self.settings.telegram_owner_id:
            return True

        if chat_id is not None and chat_id in self.settings.telegram_group_ids:
            return True

        log.info(
            "unauthorized_access",
            chat_id=chat_id,
            chat_title=chat.title if chat else None,
            user_id=user_id,
        )
        return False

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not self._is_allowed(update):
            return

        await update.message.reply_text(
            "Link Sentinel is active.\n\n"
            "Paste a GitHub or YouTube link and pick the analysis depth "
            "(Standard or Detailed). Results are always delivered as PDF.\n\n"
            "/status - Check bot config\n"
            "/help - Show this message"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not self._is_allowed(update):
            return

        await update.message.reply_text(
            "Link Sentinel\n\n"
            "Paste a link and pick Standard or Detailed. All output is PDF.\n"
            "- GitHub repo -> full analysis\n"
            "- YouTube video -> transcript summary\n"
            "- Detailed mode -> deeper analysis via a stronger model\n\n"
            "/status - Show bot config"
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not self._is_allowed(update):
            return

        groups = ", ".join(str(g) for g in self.settings.telegram_group_ids) or "None"
        await update.message.reply_text(
            f"Link Sentinel Status: Active\n\n"
            f"Owner ID: {self.settings.telegram_owner_id}\n"
            f"Group IDs: {groups}\n\n"
            f"Paths:\n"
            f"`{self.settings.github_clone_dir}`\n"
            f"`{self.settings.github_analysis_dir}`\n"
            f"`{self.settings.youtube_transcript_dir}`\n"
            f"`{self.settings.pipeline_transposed_dir}`",
            parse_mode="Markdown",
        )

    async def chatid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Reply with the current chat's ID — used to enable new groups."""
        if not self._is_allowed(update):
            return

        chat = update.effective_chat
        await update.message.reply_text(
            f"Chat ID: `{chat.id}`\n"
            f"Type: {chat.type}\n"
            f"Title: {chat.title or '(no title)'}",
            parse_mode="Markdown",
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages — detect links, ask delivery format."""
        if not update.message or not update.message.text:
            return

        if not self._is_allowed(update):
            return

        text = update.message.text
        sender_name = update.effective_user.username if update.effective_user else None
        chat_id = update.effective_chat.id
        message_id = update.message.message_id

        repos = extract_github_urls(text)
        videos = extract_youtube_urls(text)

        if not repos and not videos:
            return

        for repo in repos:
            key = f"repo_{repo.folder_name}_{chat_id}"
            self._pending[key] = {
                "type": "repo",
                "repo": repo,
                "sender_name": sender_name,
                "chat_id": chat_id,
                "message_id": message_id,
            }
            self._save_pending()

            await update.message.reply_text(
                f"Repository detected: {repo.full_name}\n"
                f"Pick analysis depth (output is always PDF):",
                reply_markup=self._depth_keyboard(key),
            )

        for video in videos:
            key = f"video_{video.video_id}_{chat_id}"
            self._pending[key] = {
                "type": "video",
                "video": {"video_id": video.video_id, "url": video.url},
                "sender_name": sender_name,
                "chat_id": chat_id,
                "message_id": message_id,
            }
            self._save_pending()

            await update.message.reply_text(
                f"YouTube video detected: {video.video_id}\n"
                f"Pick analysis depth (output is always PDF):",
                reply_markup=self._depth_keyboard(key),
            )

    @staticmethod
    def _depth_keyboard(key: str) -> InlineKeyboardMarkup:
        """Build the two-button depth keyboard — PDF is always the delivery format."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Send Standard", callback_data=f"{key}:standard"),
                InlineKeyboardButton("Send Detailed", callback_data=f"{key}:detailed"),
            ],
        ])

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle analysis depth choice — 'standard' or 'detailed'. Output is always PDF."""
        query = update.callback_query
        log.info("callback_received", data=query.data, user_id=query.from_user.id if query.from_user else None)
        await query.answer()

        if not self._is_allowed(update):
            return

        data = query.data
        if ":" not in data:
            log.warning("callback_malformed", data=data)
            return

        key, depth = data.rsplit(":", 1)
        if depth not in ANALYSIS_DEPTHS:
            log.warning("callback_unknown_depth", depth=depth)
            return

        pending = self._pending.pop(key, None)
        if not pending:
            log.warning("callback_stale", key=key)
            try:
                await query.edit_message_text("This link has expired. Send it again.")
            except Exception as e:
                log.warning("expired_edit_failed", error=str(e))
            return

        self._save_pending()

        chat_id = pending["chat_id"]
        message_id = pending["message_id"]
        sender_name = pending["sender_name"]

        if pending["type"] == "repo":
            await self._process_repo(query, pending["repo"], sender_name, chat_id, message_id, depth)
        elif pending["type"] == "video":
            video_data = pending["video"]
            video = YouTubeVideo(
                video_id=video_data["video_id"],
                url=video_data["url"],
            )
            await query.edit_message_text(
                f"YouTube video: {video.video_id}\n"
                f"Running {depth} analysis... this may take a minute."
            )
            task = asyncio.create_task(self._process_video(
                query=query,
                video=video,
                sender_name=sender_name,
                chat_id=chat_id,
                message_id=message_id,
                depth=depth,
            ))
            task.add_done_callback(self._log_task_exception)

    async def _process_repo(
        self, query, repo: GitHubRepo,
        sender_name: str | None, chat_id: int, message_id: int,
        depth: str,
    ) -> None:
        """Queue a repo analysis task. Depth picks prompt + downstream agent."""
        log.info("processing_repo", repo=repo.full_name, depth=depth)

        prompt = DETAILED_REPO_PROMPT if depth == "detailed" else REPO_PROMPT
        task_content = create_repo_analysis_task(
            repo=repo,
            clone_dir=self.settings.github_clone_dir,
            analysis_dir=self.settings.github_analysis_dir,
            sender_name=sender_name,
            user_prompt=prompt,
            analysis_depth=depth,
        )

        task_path = write_task_file(
            task_content=task_content,
            folder_name=repo.folder_name,
            task_type="repo_analysis",
            output_dir=self.settings.pipeline_transposed_dir,
        )

        log.info("task_created", path=str(task_path))

        result_path = self.settings.github_analysis_dir / f"{repo.folder_name}_analysis.md"
        track_task(
            chat_id=chat_id,
            message_id=message_id,
            task_type="repo_analysis",
            result_path=result_path,
            label=repo.full_name,
            analysis_depth=depth,
        )

        await query.edit_message_text(
            f"Repository: {repo.full_name}\n"
            f"{depth.capitalize()} analysis queued.\n"
            f"PDF will be delivered when ready."
        )

    async def _process_video(
        self, query, video: YouTubeVideo,
        sender_name: str | None, chat_id: int, message_id: int,
        depth: str,
    ) -> None:
        """Process a YouTube video — transcribe + summarize at the chosen depth, PDF-only."""
        log.info("processing_video", video_id=video.video_id, depth=depth)

        bot = query.get_bot() if query else self.application.bot

        try:
            summary, video_title = await process_video(
                url=video.url,
                video_id=video.video_id,
                transcript_dir=self.settings.youtube_transcript_dir,
                depth=depth,
            )

            title = video_title or video.video_id
            log.info("video_summarized", video_id=video.video_id, depth=depth)

            suffix = "_detailed" if depth == "detailed" else ""
            pdf_path = await markdown_to_pdf(
                summary, title,
                template="video_summary",
                metadata={
                    "video_title": title,
                    "video_url": video.url,
                    "analysis_depth": depth.capitalize(),
                },
            )
            await bot.send_document(
                chat_id=chat_id,
                document=open(pdf_path, "rb"),
                filename=f"{title.replace(' ', '_')[:50]}{suffix}_summary.pdf",
                caption=f"{depth.capitalize()} summary: {title}",
            )

        except Exception as e:
            log.error("video_processing_failed", video_id=video.video_id, error=str(e))
            await bot.send_message(
                chat_id=chat_id,
                text=f"Failed to process video {video.video_id}: {str(e)[:200]}",
            )

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Global error handler — stops exceptions from silently vanishing."""
        err = context.error
        log.error(
            "handler_error",
            error=str(err),
            error_type=type(err).__name__ if err else "unknown",
        )

    def _log_task_exception(self, task: asyncio.Task) -> None:
        """Done-callback for fire-and-forget background tasks — logs unhandled errors."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            log.error(
                "background_task_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    def build_application(self) -> Application:
        """Build and configure the Telegram application."""
        self.application = (
            Application.builder()
            .token(self.settings.telegram_bot_token)
            .build()
        )

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("chatid", self.chatid_command))
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))

        if self.settings.auto_analyze:
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )

        self.application.add_error_handler(self._error_handler)

        return self.application

    async def run(self) -> None:
        """Run the bot."""
        log.info(
            "starting_bot",
            owner_id=self.settings.telegram_owner_id,
            group_ids=self.settings.telegram_group_ids,
        )

        app = self.build_application()

        await app.initialize()
        await app.start()
        await app.updater.start_polling(
            drop_pending_updates=False,
            allowed_updates=Update.ALL_TYPES,
        )

        log.info("bot_running")

        watcher = asyncio.create_task(check_results(app))

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            log.info("stopping_bot")
            watcher.cancel()
            await app.updater.stop()
            await app.stop()
            await app.shutdown()


async def main():
    """Main entry point."""
    settings = get_settings()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

    bot = LinkSentinelBot(settings)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
