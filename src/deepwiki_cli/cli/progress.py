"""Progress display system using Enlighten library."""

import logging

import enlighten  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class ProgressManager:
    """Manages multiple progress bars for wiki generation."""

    def __init__(self) -> None:
        self.manager = enlighten.get_manager()
        self.status_bar = None
        self.overall_bar = None
        self.page_bars: dict[str, enlighten.Counter] = {}
        self.completed = 0
        self.total = 0

    def set_status(self, message: str) -> None:
        """Update the status bar message."""
        if self.status_bar is None:
            self.status_bar = self.manager.status_bar(
                status_format="{fill}Stage: {stage}{fill}{elapsed}",
                color="bold_underline_bright_white_on_lightslategray",
                justify=enlighten.Justify.CENTER,
                stage="Initializing",
                autorefresh=True,
                min_delta=0.5,
            )
        self.status_bar.update(stage=message)  # type: ignore[attr-defined]

    def init_overall_progress(self, total: int, desc: str = "Overall Progress") -> None:
        """Initialize the overall progress bar."""
        self.total = total
        self.completed = 0
        self.overall_bar = self.manager.counter(
            total=total,
            desc=desc,
            unit="pages",
            color="green",
            autorefresh=True,
            min_delta=0.1,
        )

    def add_page_progress(self, page_id: str, page_title: str) -> enlighten.Counter:
        """Add a progress bar for a specific page.

        Args:
            page_id: Unique identifier for the page
            page_title: Display title for the page

        Returns:
            Progress counter for the page
        """
        if page_id in self.page_bars:
            return self.page_bars[page_id]

        # Truncate title if too long
        display_title = page_title[:40] + "..." if len(page_title) > 40 else page_title

        counter = self.manager.counter(
            total=100,
            desc=f"  {display_title}",
            unit="%",
            color="cyan",
            leave=False,
            autorefresh=True,
            min_delta=0.1,
        )
        self.page_bars[page_id] = counter
        return counter

    def update_page_progress(self, page_id: str, progress: int) -> None:
        """Update progress for a specific page."""
        if page_id in self.page_bars:
            # Clamp progress to valid range
            progress = max(0, min(100, progress))
            self.page_bars[page_id].update(progress - self.page_bars[page_id].count)

    def complete_page(self, page_id: str) -> None:
        """Mark a page as completed."""
        if page_id in self.page_bars:
            self.page_bars[page_id].update(100 - self.page_bars[page_id].count)
            self.page_bars[page_id].close()
            del self.page_bars[page_id]

        self.completed += 1
        if self.overall_bar:
            self.overall_bar.update(1)  # type: ignore[unreachable]

    def close(self) -> None:
        """Close all progress bars and the manager."""
        # Close any remaining page bars
        for bar in list(self.page_bars.values()):
            bar.close()
        self.page_bars.clear()

        # Close overall bar
        if self.overall_bar:
            self.overall_bar.close()  # type: ignore[unreachable]
            self.overall_bar = None

        # Close status bar
        if self.status_bar:
            self.status_bar.close()  # type: ignore[unreachable]
            self.status_bar = None

        # Stop the manager
        self.manager.stop()


class SimpleProgressBar:
    """Simple progress bar for non-parallel operations."""

    def __init__(self, total: int, desc: str = "Progress") -> None:
        self.manager = enlighten.get_manager()
        self.bar = self.manager.counter(
            total=total,
            desc=desc,
            unit="items",
            color="green",
        )

    def update(self, count: int = 1) -> None:
        """Update the progress bar."""
        self.bar.update(count)

    def close(self) -> None:
        """Close the progress bar."""
        self.bar.close()
