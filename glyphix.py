import os
import random
import re
from pathlib import Path
from typing import Iterable, Optional, Tuple
from collections import deque

import lyricsgenius
import mpv
import requests
from bs4 import BeautifulSoup
from rich.text import Text

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Header, Footer, Static, Button, DirectoryTree, Label, ContentSwitcher, ListView, ListItem, Input
)

# --- Custom Widgets & Screens ---

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

class QueuePanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("Up Next", id="queue_title")
        yield ListView(id="queue_list")

    def update_queue(self, playlist: list[Path], current_index: int):
        queue_list = self.query_one(ListView)
        queue_list.clear()
        for i, track in enumerate(playlist[current_index + 1:], start=1):
            queue_list.append(ListItem(Label(f"{i}. {track.stem}")))

class LyricsPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("Lyrics", id="lyrics_title")
        with VerticalScroll(id="lyrics_container"):
            yield Static("No song playing.", id="lyrics_content", classes="lyrics-text")

    def update_lyrics(self, text: str, is_manual_prompt: bool = False):
        content = self.query_one("#lyrics_content", Static)
        content.update(text)
        title_label = self.query_one("#lyrics_title", Label)
        title_label.update("Lyrics Input URL" if is_manual_prompt else "Lyrics")

class UrlInputScreen(ModalScreen[str]):
    def compose(self) -> ComposeResult:
        with Vertical(id="url_input_dialog"):
            yield Label("Enter Genius.com Lyrics URL")
            yield Input(placeholder="https://genius.com/...", id="url_input")
            with Horizontal(id="url_input_buttons"):
                yield Button("Import", variant="primary", id="import_button")
                yield Button("Cancel", id="cancel_button")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import_button":
            url = self.query_one(Input).value
            if url and "genius.com" in url:
                self.dismiss(url)
            else:
                self.app.bell()
        else:
            self.dismiss()

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}

class AudioDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if path.is_dir() or path.suffix.lower() in AUDIO_EXTENSIONS]

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
                path = tree.cursor_node.data.path
                if path.is_dir(): self.dismiss(path)
                else: self.app.bell()
            else: self.app.bell()
        else:
            self.dismiss()

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.dismiss(event.path)

class FolderTab(Button):
    def __init__(self, label: str, path: Path) -> None:
        super().__init__(label, classes="folder_tab")
        self.path = path

MUSIC_PATH = Path(os.path.expanduser("~/Music"))
GENIUS_TOKEN = "mifcQJWnPhpj57bygLxgddWHa9gMw0KXYc4d0XZcznZ2SJBBFUASXKYdKz0olTVK"

class GlyphixApp(App):
    CSS_PATH = "glyphix.css"

    BINDINGS = [
        Binding("space", "play_pause", "Play/Pause", priority=True),
        Binding("n", "next_track", "Next"),
        Binding("p", "prev_track", "Previous"),
        Binding("s", "toggle_shuffle", "Shuffle"),
        Binding("r", "toggle_repeat", "Repeat"),
        Binding("a", "add_folder", "Add Folder"),
        Binding("d", "close_folder", "Close Folder"),
        Binding("l", "toggle_lyrics_queue", "Lyrics/Queue"),
        Binding("i", "import_lyrics", "Import Lyrics", show=False),
        Binding("q", "quit", "Quit"),
    ]

    playlist: list[Path] = []
    original_playlist: list[Path] = []
    current_track_index: int = -1

    is_shuffled = reactive(False)
    is_repeat_on = reactive(False)

    def __init__(self):
        super().__init__()
        self.debug_log_messages = deque(maxlen=10)
        self.playback = mpv.MPV(log_handler=self._log_handler, input_default_bindings=False, idle='yes')
        self._is_player_active = False
        self.playback.observe_property('filename', self._on_track_change)
        self.genius = lyricsgenius.Genius(GENIUS_TOKEN, verbose=False, remove_section_headers=True)
        self.manual_lyrics_prompt = False

    def _log_handler(self, level: str, prefix: str, text: str) -> None:
        self.debug_log_messages.append(f"[{level}] {prefix}: {text.strip()}")
        self.call_from_thread(self._update_debug_log)

    def _update_debug_log(self) -> None:
        try:
            log_widget = self.query_one("#debug_log", Static)
            log_widget.update("\n".join(self.debug_log_messages))
        except Exception:
            pass

    def _on_track_change(self, name: str, new_filename: Optional[str]) -> None:
        if new_filename:
            try:
                new_index = next(i for i, path in enumerate(self.playlist) if path.name == new_filename)
                self.call_from_thread(self._handle_track_change_on_main_thread, new_index)
            except StopIteration:
                pass

    def _handle_track_change_on_main_thread(self, new_index: int) -> None:
        self.current_track_index = new_index
        self.update_track_display()
        self.fetch_lyrics()

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
                            yield SeekSlider(id="seek_slider")
                    with Horizontal(id="music_controls"):
                        yield Button("🔀",id="shuffle_button")
                        yield Button("⏮",id="prev_button")
                        yield Button("▶",id="play_pause_button")
                        yield Button("⏭",id="next_button")
                        yield Button("🔁",id="loop_button")
                with ContentSwitcher(initial="queue_panel", id="lyrics_queue_switcher"):
                    yield QueuePanel(id="queue_panel")
                    yield LyricsPanel(id="lyrics_panel")
                yield Static(id="debug_log", classes="log-panel")
        yield Footer()

    def on_mount(self) -> None:
        self.add_folder_tab(MUSIC_PATH)
        self.query_one("#debug_log", Static).border_title = "MPV Log"
        self.set_interval(0.5, self.update_seek_slider)

    def on_unmount(self) -> None:
        self.playback.terminate()

    def watch_is_shuffled(self, is_shuffled: bool) -> None:
        self.query_one("#shuffle_button").classes = "active" if is_shuffled else ""

    def watch_is_repeat_on(self, is_repeat_on: bool) -> None:
        self.playback.loop_file = 'inf' if is_repeat_on else 'no'
        self.query_one("#loop_button").classes = "active" if is_repeat_on else ""

    def play_track(self, track_path: Path):
        # *** THE FIX IS HERE ***
        # Clear the old playlist and start with the selected track.
        self.playback.loadfile(str(track_path), mode='replace')
        self.playback.pause = False
        self._is_player_active = True

        # Now, append the rest of the songs to mpv's internal playlist.
        # This ensures 'next' and 'previous' work correctly.
        if 0 <= self.current_track_index < len(self.playlist):
            for i in range(self.current_track_index + 1, len(self.playlist)):
                self.playback.playlist_append(str(self.playlist[i]))

        # Update the UI now that playback has started.
        self.update_track_display()
        self.fetch_lyrics()

    def update_track_display(self):
        if 0 <= self.current_track_index < len(self.playlist):
            track_path = self.playlist[self.current_track_index]
            self.query_one("#music_name", Label).update(track_path.stem)
            self.query_one("#play_pause_button", Button).label = "⏸"
            slider = self.query_one(SeekSlider)
            def get_duration():
                duration = self.playback.duration
                slider.max_value = float(duration if duration is not None else 100.0)
            self.set_timer(0.1, get_duration)
            self.query_one(QueuePanel).update_queue(self.playlist, self.current_track_index)

    def update_seek_slider(self) -> None:
        if self._is_player_active:
            duration = self.playback.duration
            time_pos = self.playback.time_pos
            if duration is not None and time_pos is not None:
                slider = self.query_one(SeekSlider)
                slider.max_value = float(duration)
                slider.value = float(time_pos)
            play_pause_button = self.query_one("#play_pause_button", Button)
            play_pause_button.label = "⏸" if not self.playback.pause else "▶"

    def on_seek_slider_seek(self, message: SeekSlider.Seek) -> None:
        if self._is_player_active: self.playback.seek(message.seek_time, reference='absolute')

    def action_toggle_lyrics_queue(self) -> None:
        switcher = self.query_one(ContentSwitcher)
        switcher.current = "lyrics_panel" if switcher.current == "queue_panel" else "queue_panel"

    def action_play_pause(self) -> None:
        if self._is_player_active: self.playback.pause = not self.playback.pause
        else: self.bell()

    def action_toggle_shuffle(self) -> None:
        self.is_shuffled = not self.is_shuffled
        if not self.playlist or self.current_track_index == -1: return
        current_song = self.playlist[self.current_track_index]
        if self.is_shuffled:
            self.original_playlist = self.playlist[:]
            rest_of_playlist = [p for p in self.playlist if p != current_song]
            random.shuffle(rest_of_playlist)
            self.playlist = [current_song] + rest_of_playlist
        else:
            if not self.original_playlist: return
            self.playlist = self.original_playlist[:]
        self.current_track_index = self.playlist.index(current_song)
        # Rebuild the MPV queue
        self.playback.playlist_clear()
        for i in range(self.current_track_index + 1, len(self.playlist)):
            self.playback.playlist_append(str(self.playlist[i]))
        # Update the UI queue
        self.query_one(QueuePanel).update_queue(self.playlist, self.current_track_index)

    def action_toggle_repeat(self) -> None:
        self.is_repeat_on = not self.is_repeat_on

    def action_next_track(self) -> None:
        self.playback.playlist_next()

    def action_prev_track(self) -> None:
        self.playback.playlist_prev()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = event.path
        parent_dir = path.parent
        self.playlist = sorted([p for p in parent_dir.iterdir() if p.suffix.lower() in AUDIO_EXTENSIONS])
        self.original_playlist = []
        if self.is_shuffled:
            self.original_playlist = self.playlist[:]
            current_song = path
            rest_of_playlist = [p for p in self.playlist if p != current_song]
            random.shuffle(rest_of_playlist)
            self.playlist = [current_song] + rest_of_playlist
        try:
            self.current_track_index = self.playlist.index(path)
            self.play_track(path)
        except ValueError:
            self._is_player_active = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, FolderTab): self.set_active_tab(event.button)
        elif event.button.id == "play_pause_button": self.action_play_pause()
        elif event.button.id == "next_button": self.action_next_track()
        elif event.button.id == "prev_button": self.action_prev_track()
        elif event.button.id == "shuffle_button": self.action_toggle_shuffle()
        elif event.button.id == "loop_button": self.action_toggle_repeat()
        else: self.bell()

    def _parse_artist_title(self, filename: str) -> Tuple[Optional[str], str]:
        clean_filename = filename.replace("_", " ")
        clean_filename = re.sub(r'\s*\(.*?\)', '', clean_filename).strip()
        parts = clean_filename.split(" - ", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return None, clean_filename

    def _set_manual_prompt(self, value: bool) -> None:
        self.manual_lyrics_prompt = value

    def fetch_lyrics(self):
        self._set_manual_prompt(False)
        lyrics_panel = self.query_one(LyricsPanel)
        if 0 <= self.current_track_index < len(self.playlist):
            track_path = self.playlist[self.current_track_index]
            lyrics_panel.update_lyrics(f"Fetching lyrics for {track_path.stem}...")
            artist, title = self._parse_artist_title(track_path.stem)
            self.get_lyrics_from_genius(title, artist)
        else:
            lyrics_panel.update_lyrics("No song playing.")

    @work(exclusive=True, thread=True)
    def get_lyrics_from_genius(self, title: str, artist: Optional[str]):
        lyrics_panel = self.query_one(LyricsPanel)
        try:
            song = self.genius.search_song(title, artist if artist else "")
            if song and song.lyrics:
                lyrics_text = re.sub(r'\[.*?\]', '', song.lyrics).strip()
                self.call_from_thread(lyrics_panel.update_lyrics, lyrics_text)
                self.call_from_thread(self._set_manual_prompt, False)
            else:
                raise ValueError("Lyrics not found")
        except Exception:
            fail_message = "Could not fetch lyrics. Import Manually? ('i')"
            self.call_from_thread(lyrics_panel.update_lyrics, fail_message, is_manual_prompt=True)
            self.call_from_thread(self._set_manual_prompt, True)

    @work(exclusive=True, thread=True)
    def scrape_lyrics_from_url(self, url: str):
        lyrics_panel = self.query_one(LyricsPanel)
        self.call_from_thread(lyrics_panel.update_lyrics, f"Scraping lyrics from {url}...")
        try:
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
            }
            page = requests.get(url, headers=headers, timeout=10)
            page.raise_for_status()
            soup = BeautifulSoup(page.text, 'html.parser')
            lyrics_containers = soup.find_all("div", {"data-lyrics-container": "true"})
            if not lyrics_containers:
                raise ValueError("Lyrics container not found on page.")

            all_lyrics = [c.get_text(separator="\n") for c in lyrics_containers]
            lyrics_text = "\n\n".join(all_lyrics).strip()

            if not lyrics_text:
                raise ValueError("Scraped lyrics text is empty.")

            self.call_from_thread(lyrics_panel.update_lyrics, lyrics_text)
            self.call_from_thread(self._set_manual_prompt, False)
        except Exception as e:
            self.call_from_thread(lyrics_panel.update_lyrics, f"Failed to scrape lyrics: {e}", is_manual_prompt=True)
            self.call_from_thread(self._set_manual_prompt, True)

    def action_import_lyrics(self) -> None:
        if self.manual_lyrics_prompt and self.query_one(ContentSwitcher).current == "lyrics_panel":
            def url_callback(url: Optional[str]):
                if url:
                    self.scrape_lyrics_from_url(url)
            self.push_screen(UrlInputScreen(), url_callback)
        else:
            self.bell()

    def set_active_tab(self, tab: FolderTab) -> None:
        for t in self.query(FolderTab): t.remove_class("active")
        tab.add_class("active")
        self.query_one(AudioDirectoryTree).path = str(tab.path)

    def add_folder_tab(self, path: Path, make_active: bool = True) -> None:
        for tab in self.query(FolderTab):
            if tab.path == path:
                self.set_active_tab(tab)
                return
        new_tab = FolderTab(path.name, path)
        self.query_one("#left_panel").mount(new_tab)
        if make_active: self.set_active_tab(new_tab)

    def action_add_folder(self) -> None:
        def callback(path: Optional[Path]):
            if path: self.add_folder_tab(path, True)
        self.push_screen(SelectDirectoryScreen(), callback)

    def action_close_folder(self) -> None:
        tabs = list(self.query(FolderTab))
        if len(tabs) <= 1:
            self.bell()
            return
        active_tabs = self.query(".folder_tab.active")
        if active_tabs:
            active_tabs.first().remove()
            remaining_tabs = self.query(FolderTab)
            if remaining_tabs: self.set_active_tab(remaining_tabs.first())

if __name__ == "__main__":
    app = GlyphixApp()
    app.run()
