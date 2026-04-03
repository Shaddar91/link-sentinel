"""Configuration settings for Link Sentinel."""
import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    #Telegram Bot Configuration
    telegram_bot_token: str = Field(..., description="Telegram bot API token")
    telegram_owner_id: int = Field(..., description="Your Telegram user ID (bot always responds to you)")
    telegram_group_id: int | None = Field(default=None, description="Group chat ID where the bot also responds")

    #AI Task Automation Pipeline Paths
    pipeline_transposed_dir: Path = Field(
        default=Path("/home/shaddar/Documents/workspace/ai-task-automation/data/pipeline/transposed"),
        description="Directory for pipeline task files"
    )

    #GitHub Repository Paths
    github_clone_dir: Path = Field(
        default=Path("/home/shaddar/Documents/workspace/personal/projects/github/repo-analysis/cloned"),
        description="Directory where GitHub repos are cloned for analysis"
    )
    github_analysis_dir: Path = Field(
        default=Path("/home/shaddar/Documents/workspace/personal/projects/github/repo-analysis/analysis-docs"),
        description="Directory where repo analysis documents are saved"
    )

    #YouTube Transcript Paths
    youtube_transcript_dir: Path = Field(
        default=Path(os.path.expanduser("~/.transcribes")),
        description="Directory where YouTube transcripts are saved"
    )

    #Processing Options
    auto_analyze: bool = Field(
        default=True,
        description="Automatically trigger analysis when link detected"
    )

    #Logging
    log_level: str = Field(default="INFO", description="Logging level")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
