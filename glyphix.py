import os
from pathlib import Path
from typing import Iterable

from just_playback import Playback

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static, Button, DirectoryTree, Label
from textual_slider import Slider

# --- Helper Data and Custom Widgets ---

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}

class AudioDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path
            for path in paths
            if path.is_dir() or path.suffix.lower() in AUDIO_EXTENSIONS
        ]

class SelectDirectoryScreen(ModalScreen[Path]):
    def compose(self) -> ComposeResult:
        with Vertical(id="select_directory_dialog"):
            yield Label("Select a Music Folder")
            yield DirectoryTree(os.path.expanduser("~"), id="select_directory_tree")
            with Horizontal(id="select_directory_buttons"):
                yield Button("Select", variant="primary", id="select_button")
                yield Button("Cancel", id="cancel_button")

    def on_mount(self) -> None:
        self.query_one(DirectoryTree).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select_button":
            tree = self.query_one(DirectoryTree)
            if tree.cursor_node and tree.cursor_node.data:
                selected_path = tree.cursor_node.data.path
                if selected_path.is_dir():
                    self.dismiss(selected_path)
                else:
                    self.app.bell()
            else:
                self.app.bell()
        else:
            self.dismiss()

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.dismiss(event.path)


class FolderTab(Button):
    def __init__(self, label: str, path: Path) -> None:
        super().__init__(label, classes="folder_tab")
        self.path = path

MUSIC_PATH = Path(os.path.expanduser("~/Music"))

class GlyphixApp(App):
    """A TUI music player called glyphix."""

    CSS_PATH = "glyphix.css"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("a", "add_folder", "Add Folder"),
        Binding("d", "close_folder", "Close Folder"),
        Binding("space", "play_pause", "Play/Pause"),
        Binding("n", "next_track", "Next"),
        Binding("p", "prev_track", "Previous"),
    ]

    playlist: list[Path] = []
    current_track_index: int = -1

    def __init__(self):
        super().__init__()
        self.playback = Playback()

    def compose(self) -> ComposeResult:
        yield Header(name="glyphix")
        with Container(id="main_container"):
            yield Vertical(id="left_panel")
            with Vertical(id="middle_panel"):
                yield AudioDirectoryTree(str(MUSIC_PATH), id="music_tree_panel")
            with Vertical(id="right_panel"):
                with Vertical(id="player_panel"):
                    with Horizontal(id="player_top_section"):
                        yield Static("🎵", id="album_art")
                        with Vertical(id="track_info"):
                            yield Label("Select a song...", id="music_name")
                            yield Slider(min=0, max=100, step=1, id="seek_slider")
                    with Horizontal(id="music_controls"):
                        yield Button("🔀", id="shuffle_button")
                        yield Button("⏮", id="prev_button")
                        yield Button("▶", id="play_pause_button")
                        yield Button("⏭", id="next_button")
                        yield Button("🔁", id="loop_button")
                yield Static("Lyrics/Queue Panel (toggleable)", id="lyrics_queue_panel")
        yield Footer()

    def on_mount(self) -> None:
        self.add_folder_tab(MUSIC_PATH, make_active=True)
        self.set_interval(0.5, self.update_seek_slider)

    def on_unmount(self) -> None:
        self.playback.stop()

    def play_track(self, track_path: Path):
        self.playback.stop()
        self.playback.load_file(str(track_path))
        self.playback.play()
        self.query_one("#music_name", Label).update(track_path.stem)
        self.query_one("#play_pause_button", Button).label = "⏸"
        if self.playback.duration > 0:
            self.query_one("#seek_slider", Slider).max = int(self.playback.duration)
        else:
            self.query_one("#seek_slider", Slider).max = 100

    def update_seek_slider(self) -> None:
        """Automatically updates the slider's position based on song progress."""
        if self.playback.active:
            slider = self.query_one("#seek_slider", Slider)
            # Update the slider's value to reflect the current song position.
            slider.value = int(self.playback.curr_pos)

            # Automatically play the next track if the current one has finished.
            if not self.playback.playing and self.playback.curr_pos >= self.playback.duration - 0.5:
                 self.action_next_track()

    def on_slider_changed(self, event: Slider.Changed) -> None:
        """Handles manual seeking when the user interacts with the slider."""
        # FIX: Only seek if the slider's value is different from the playback's
        # current position. This prevents the automatic update from causing a stutter.
        if self.playback.active and int(self.playback.curr_pos) != event.value:
            self.playback.seek(event.value)

    def action_play_pause(self) -> None:
        if self.playback.active:
            if self.playback.paused:
                self.playback.resume()
                self.query_one("#play_pause_button", Button).label = "⏸"
            else:
                self.playback.pause()
                self.query_one("#play_pause_button", Button).label = "▶"
        else:
            self.bell()

    def action_next_track(self) -> None:
        if not self.playlist:
            self.bell()
            return
        self.current_track_index = (self.current_track_index + 1) % len(self.playlist)
        track_to_play = self.playlist[self.current_track_index]
        self.play_track(track_to_play)

    def action_prev_track(self) -> None:
        if not self.playlist:
            self.bell()
            return
        self.current_track_index = (self.current_track_index - 1 + len(self.playlist)) % len(self.playlist)
        track_to_play = self.playlist[self.current_track_index]
        self.play_track(track_to_play)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        selected_path = event.path
        parent_dir = selected_path.parent
        self.playlist = sorted([p for p in parent_dir.iterdir() if p.suffix.lower() in AUDIO_EXTENSIONS])
        try:
            self.current_track_index = self.playlist.index(selected_path)
            self.play_track(selected_path)
        except ValueError:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, FolderTab):
            self.set_active_tab(event.button)
        elif event.button.id == "play_pause_button":
            self.action_play_pause()
        elif event.button.id == "next_button":
            self.action_next_track()
        elif event.button.id == "prev_button":
            self.action_prev_track()
        else:
            self.bell()

    def set_active_tab(self, tab_to_activate: FolderTab) -> None:
        for tab in self.query(FolderTab):
            tab.remove_class("active")
        tab_to_activate.add_class("active")
        self.query_one(AudioDirectoryTree).path = str(tab_to_activate.path)

    def add_folder_tab(self, path: Path, make_active: bool = True) -> None:
        for tab in self.query(FolderTab):
            if tab.path == path:
                self.set_active_tab(tab)
                return
        new_tab = FolderTab(path.name, path)
        self.query_one("#left_panel").mount(new_tab)
        if make_active:
            self.set_active_tab(new_tab)

    def action_add_folder(self) -> None:
        def handle_directory_selected(path: Path | None):
            if path:
                self.add_folder_tab(path, make_active=True)
        self.push_screen(SelectDirectoryScreen(), handle_directory_selected)

    def action_close_folder(self) -> None:
        all_tabs = list(self.query(FolderTab))
        active_tabs = self.query(".folder_tab.active")
        if len(all_tabs) <= 1:
            self.bell()
            return
        if active_tabs:
            active_tab = active_tabs.first()
            active_tab.remove()
            remaining_tabs = self.query(FolderTab)
            if remaining_tabs:
                self.set_active_tab(remaining_tabs.first())


if __name__ == "__main__":
    app = GlyphixApp()
    app.run()
