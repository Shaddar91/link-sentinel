"""Telegram bot for monitoring GitHub and YouTube links."""
import asyncio
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
from .result_watcher import track_task, check_results, md_to_pdf, split_message
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

VIDEO_PROMPT = (
    "Summarize this video:\n\n"
    "1. What is the video about? (one paragraph)\n"
    "2. Key points and main takeaways.\n"
    "3. Any technical details or explanations worth noting.\n"
    "4. Actionable steps or practical advice mentioned.\n"
    "5. Who is this useful for?\n\n"
    "Be concise and structured."
)


class LinkSentinelBot:
    """Telegram bot that monitors channels for GitHub and YouTube links."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.application: Application = None
        # Pending links waiting for delivery format choice
        self._pending: dict[str, dict] = {}

    def _is_allowed(self, update: Update) -> bool:
        """Check if the message comes from an allowed chat."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id if update.effective_user else None

        if user_id == self.settings.telegram_owner_id:
            return True

        if self.settings.telegram_group_id and chat_id == self.settings.telegram_group_id:
            return True

        log.info("unauthorized_access", chat_id=chat_id, user_id=user_id)
        return False

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not self._is_allowed(update):
            return

        await update.message.reply_text(
            "Link Sentinel is active.\n\n"
            "Paste a GitHub or YouTube link, pick how you want the results "
            "(messages or PDF), and I'll queue the task.\n\n"
            "/status - Check bot config\n"
            "/help - Show this message"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not self._is_allowed(update):
            return

        await update.message.reply_text(
            "Link Sentinel\n\n"
            "Just paste a link and choose delivery format:\n"
            "- GitHub repo -> full analysis\n"
            "- YouTube video -> summary\n\n"
            "/status - Show bot config"
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not self._is_allowed(update):
            return

        await update.message.reply_text(
            f"Link Sentinel Status: Active\n\n"
            f"Owner ID: {self.settings.telegram_owner_id}\n"
            f"Group ID: {self.settings.telegram_group_id or 'Not set'}\n\n"
            f"Paths:\n"
            f"`{self.settings.github_clone_dir}`\n"
            f"`{self.settings.github_analysis_dir}`\n"
            f"`{self.settings.youtube_transcript_dir}`\n"
            f"`{self.settings.pipeline_transposed_dir}`",
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

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Send as messages", callback_data=f"{key}:msg"),
                    InlineKeyboardButton("Send as PDF", callback_data=f"{key}:pdf"),
                ],
            ])

            await update.message.reply_text(
                f"Repository detected: {repo.full_name}\n"
                f"How do you want the results?",
                reply_markup=keyboard,
            )

        for video in videos:
            await update.message.reply_text(
                f"YouTube video detected: {video.video_id}\n"
                f"Transcribing and summarizing... this may take a minute."
            )
            await self._process_video(
                query=None,
                video=video,
                sender_name=sender_name,
                chat_id=chat_id,
                message_id=message_id,
                delivery_format="pdf",
            )

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle delivery format choice."""
        query = update.callback_query
        await query.answer()

        if not self._is_allowed(update):
            return

        data = query.data
        if ":" not in data:
            return

        key, delivery_format = data.rsplit(":", 1)

        pending = self._pending.pop(key, None)
        if not pending:
            await query.edit_message_text("This link has expired. Send it again.")
            return

        chat_id = pending["chat_id"]
        message_id = pending["message_id"]
        sender_name = pending["sender_name"]

        if pending["type"] == "repo":
            repo = pending["repo"]
            await self._process_repo(query, repo, sender_name, chat_id, message_id, delivery_format)

    async def _process_repo(
        self, query, repo: GitHubRepo,
        sender_name: str | None, chat_id: int, message_id: int,
        delivery_format: str,
    ) -> None:
        """Process a detected GitHub repository."""
        log.info("processing_repo", repo=repo.full_name, delivery=delivery_format)

        task_content = create_repo_analysis_task(
            repo=repo,
            clone_dir=self.settings.github_clone_dir,
            analysis_dir=self.settings.github_analysis_dir,
            sender_name=sender_name,
            user_prompt=REPO_PROMPT,
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
            delivery_format=delivery_format,
        )

        fmt = "PDF file" if delivery_format == "pdf" else "messages"
        await query.edit_message_text(
            f"Repository: {repo.full_name}\n"
            f"Analysis task queued.\n"
            f"Results will be sent as {fmt} when ready."
        )

    async def _process_video(
        self, query, video: YouTubeVideo,
        sender_name: str | None, chat_id: int, message_id: int,
        delivery_format: str,
    ) -> None:
        """Process a YouTube video — transcribe + summarize, always PDF."""
        log.info("processing_video", video_id=video.video_id, delivery=delivery_format)

        bot = query.get_bot() if query else self.application.bot

        try:
            summary, video_title = await process_video(
                url=video.url,
                video_id=video.video_id,
                transcript_dir=self.settings.youtube_transcript_dir,
            )

            title = video_title or video.video_id
            log.info("video_summarized", video_id=video.video_id)

            pdf_path = md_to_pdf(summary, title)
            await bot.send_document(
                chat_id=chat_id,
                document=open(pdf_path, "rb"),
                filename=f"{title.replace(' ', '_')[:50]}_summary.pdf",
                caption=f"Summary: {title}",
            )

        except Exception as e:
            log.error("video_processing_failed", video_id=video.video_id, error=str(e))
            await bot.send_message(
                chat_id=chat_id,
                text=f"Failed to process video {video.video_id}: {str(e)[:200]}",
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
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))

        if self.settings.auto_analyze:
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )

        return self.application

    async def run(self) -> None:
        """Run the bot."""
        log.info(
            "starting_bot",
            owner_id=self.settings.telegram_owner_id,
            group_id=self.settings.telegram_group_id,
        )

        app = self.build_application()

        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

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
