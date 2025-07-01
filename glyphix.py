import os
from pathlib import Path
from typing import Iterable

from just_playback import Playback

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Header, Footer, Static, Button, DirectoryTree, Label, ContentSwitcher, ListView, ListItem
)

# --- Custom Seek Slider Widget ---

class SeekSlider(Static, can_focus=True):
    class Seek(Message):
        def __init__(self, seek_time: float) -> None:
            self.seek_time = seek_time
            super().__init__()

    value = reactive(0.0, layout=True)
    max_value = reactive(100.0, layout=True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._is_dragging: bool = False

    def render(self) -> Text:
        width = self.size.width
        if width == 0 or self.max_value == 0: return Text("")
        percent_complete = self.value / self.max_value
        handle_pos = int(percent_complete * (width - 1))
        bar = Text()
        bar.append("─" * handle_pos, style="bold cyan")
        bar.append("●", style="bold white")
        bar.append("─" * (width - handle_pos - 1), style="bold grey39")
        return bar

    def _post_seek_message(self, event: events.MouseEvent) -> None:
        percent = max(0.0, min(1.0, event.x / self.size.width))
        seek_time = percent * self.max_value
        self.post_message(self.Seek(seek_time))
        self.value = seek_time

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._is_dragging = True
        self.capture_mouse(); self._post_seek_message(event)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._is_dragging: self._post_seek_message(event)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self._is_dragging = False
        self.release_mouse()

# --- Other Custom Widgets ---

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}

class QueuePanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("Up Next", id="queue_title"); yield ListView(id="queue_list")
    def update_queue(self, playlist: list[Path], current_index: int):
        queue_list = self.query_one(ListView); queue_list.clear()
        for track in playlist[current_index + 1:]: queue_list.append(ListItem(Label(track.stem)))

class LyricsPanel(Static):
    def compose(self) -> ComposeResult: yield Label("Lyrics will be shown here.", id="lyrics_placeholder")

class AudioDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if path.is_dir() or path.suffix.lower() in AUDIO_EXTENSIONS]

class SelectDirectoryScreen(ModalScreen[Path]):
    def compose(self) -> ComposeResult:
        with Vertical(id="select_directory_dialog"):
            yield Label("Select a Music Folder"); yield DirectoryTree(os.path.expanduser("~"), id="select_directory_tree")
            with Horizontal(id="select_directory_buttons"):
                yield Button("Select", variant="primary", id="select_button"); yield Button("Cancel", id="cancel_button")
    def on_mount(self) -> None: self.query_one(DirectoryTree).focus()
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select_button":
            tree = self.query_one(DirectoryTree)
            if tree.cursor_node and tree.cursor_node.data:
                path = tree.cursor_node.data.path
                if path.is_dir(): self.dismiss(path)
                else: self.app.bell()
            else: self.app.bell()
        else: self.dismiss()
    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None: self.dismiss(event.path)

class FolderTab(Button):
    def __init__(self, label: str, path: Path) -> None:
        super().__init__(label, classes="folder_tab"); self.path = path

MUSIC_PATH = Path(os.path.expanduser("~/Music"))

class GlyphixApp(App):
    CSS_PATH = "glyphix.css"

    # FIX: Add 'priority=True' to the space binding. This ensures it's always
    # active and visible in the footer, even when DirectoryTree is focused.
    BINDINGS = [
        Binding("space", "play_pause", "Play/Pause", priority=True),
        Binding("n", "next_track", "Next"),
        Binding("p", "prev_track", "Previous"),
        Binding("a", "add_folder", "Add Folder"),
        Binding("d", "close_folder", "Close Folder"),
        Binding("l", "toggle_lyrics_queue", "Lyrics/Queue"),
        Binding("q", "quit", "Quit"),
    ]

    playlist: list[Path] = []; current_track_index: int = -1

    def __init__(self):
        super().__init__()
        self.playback = Playback()

    def compose(self) -> ComposeResult:
        yield Header(name="glyphix")
        with Container(id="main_container"):
            yield Vertical(id="left_panel")
            with Vertical(id="middle_panel"): yield AudioDirectoryTree(str(MUSIC_PATH), id="music_tree_panel")
            with Vertical(id="right_panel"):
                with Vertical(id="player_panel"):
                    with Horizontal(id="player_top_section"):
                        yield Static("🎵", id="album_art")
                        with Vertical(id="track_info"):
                            yield Label("Select a song...", id="music_name")
                            yield SeekSlider(id="seek_slider")
                    with Horizontal(id="music_controls"):
                        yield Button("🔀",id="shuffle_button"); yield Button("⏮",id="prev_button"); yield Button("▶",id="play_pause_button"); yield Button("⏭",id="next_button"); yield Button("🔁",id="loop_button")
                with ContentSwitcher(initial="queue_panel", id="lyrics_queue_switcher"):
                    yield QueuePanel(id="queue_panel"); yield LyricsPanel(id="lyrics_panel")
        yield Footer()

    def on_mount(self) -> None:
        self.add_folder_tab(MUSIC_PATH)
        self.set_interval(0.5, self.update_seek_slider)

    def on_unmount(self) -> None: self.playback.stop()

    def play_track(self, track_path: Path):
        self.playback.stop()
        self.playback.load_file(str(track_path))
        self.playback.play()
        self.query_one("#music_name", Label).update(track_path.stem)
        self.query_one("#play_pause_button", Button).label = "⏸"
        slider = self.query_one(SeekSlider)
        slider.max_value = self.playback.duration if self.playback.duration > 0 else 100
        self.query_one(QueuePanel).update_queue(self.playlist, self.current_track_index)

    def update_seek_slider(self) -> None:
        if self.playback.active:
            slider = self.query_one(SeekSlider)
            slider.value = self.playback.curr_pos
            if not self.playback.playing and self.playback.curr_pos >= self.playback.duration - 0.5:
                self.action_next_track()

    # The on_key handler is no longer needed. The prioritized binding handles it.

    def on_seek_slider_seek(self, message: SeekSlider.Seek) -> None:
        if self.playback.active: self.playback.seek(message.seek_time)

    def action_toggle_lyrics_queue(self) -> None:
        switcher = self.query_one(ContentSwitcher)
        switcher.current = "lyrics_panel" if switcher.current == "queue_panel" else "queue_panel"

    def action_play_pause(self) -> None:
        if self.playback.active:
            play_pause_button = self.query_one("#play_pause_button", Button)
            if self.playback.paused:
                self.playback.resume()
                play_pause_button.label = "⏸"
            else:
                self.playback.pause()
                play_pause_button.label = "▶"
        else: self.bell()

    def action_next_track(self) -> None:
        if not self.playlist: self.bell(); return
        self.current_track_index = (self.current_track_index + 1) % len(self.playlist)
        self.play_track(self.playlist[self.current_track_index])

    def action_prev_track(self) -> None:
        if not self.playlist: self.bell(); return
        self.current_track_index = (self.current_track_index - 1 + len(self.playlist)) % len(self.playlist)
        self.play_track(self.playlist[self.current_track_index])

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = event.path
        parent_dir = path.parent
        self.playlist = sorted([p for p in parent_dir.iterdir() if p.suffix.lower() in AUDIO_EXTENSIONS])
        try:
            self.current_track_index = self.playlist.index(path)
            self.play_track(path)
        except ValueError: pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, FolderTab): self.set_active_tab(event.button)
        elif event.button.id == "play_pause_button": self.action_play_pause()
        elif event.button.id == "next_button": self.action_next_track()
        elif event.button.id == "prev_button": self.action_prev_track()
        else: self.bell()

    def set_active_tab(self, tab: FolderTab) -> None:
        for t in self.query(FolderTab): t.remove_class("active")
        tab.add_class("active"); self.query_one(AudioDirectoryTree).path = str(tab.path)

    def add_folder_tab(self, path: Path, make_active: bool = True) -> None:
        for tab in self.query(FolderTab):
            if tab.path == path: self.set_active_tab(tab); return
        new_tab = FolderTab(path.name, path)
        self.query_one("#left_panel").mount(new_tab)
        if make_active: self.set_active_tab(new_tab)

    def action_add_folder(self) -> None:
        def callback(path: Path | None):
            if path: self.add_folder_tab(path, True)
        self.push_screen(SelectDirectoryScreen(), callback)

    def action_close_folder(self) -> None:
        tabs = list(self.query(FolderTab))
        if len(tabs) <= 1: self.bell(); return
        active_tabs = self.query(".folder_tab.active")
        if active_tabs:
            active_tabs.first().remove()
            remaining_tabs = self.query(FolderTab)
            if remaining_tabs: self.set_active_tab(remaining_tabs.first())

if __name__ == "__main__":
    app = GlyphixApp()
    app.run()
