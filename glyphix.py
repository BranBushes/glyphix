import os
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Button, DirectoryTree, Label
from textual_slider import Slider
from textual.binding import Binding

# Set a starting path for the DirectoryTree
MUSIC_PATH = os.path.expanduser("~/Music")

class GlyphixApp(App):
    """A TUI music player called glyphix."""

    CSS_PATH = "glyphix.css"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "play_pause", "Play/Pause", show=False),
        Binding("n", "next_track", "Next", show=False),
        Binding("p", "prev_track", "Previous", show=False),
        Binding("s", "shuffle", "Shuffle", show=False),
        Binding("r", "repeat", "Repeat", show=False),
        Binding("l", "toggle_lyrics", "Lyrics/Queue", show=False),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(name="glyphix")

        with Container(id="main_container"):
            # Left panel for music folder tabs
            with Vertical(id="left_panel"):
                yield Button("Music Folder 1", id="folder_tab_1", classes="folder_tab active")
                yield Button("Music Folder 2", id="folder_tab_2", classes="folder_tab")
                yield Button("Music Folder 3", id="folder_tab_3", classes="folder_tab")

            # Middle panel for the music file tree
            with Vertical(id="middle_panel"):
                yield DirectoryTree(MUSIC_PATH, id="music_tree_panel")

            # Right panel for player and lyrics/queue
            with Vertical(id="right_panel"):
                with Vertical(id="player_panel"):
                    with Horizontal(id="player_top_section"):
                        yield Static("🎵", id="album_art")
                        with Vertical(id="track_info"):
                            yield Label("Music Name", id="music_name")
                            # FIX: Add min and max parameters to the Slider
                            yield Slider(min=0, max=100, id="seek_slider")

                    with Horizontal(id="music_controls"):
                        yield Button("🔀", id="shuffle_button")
                        yield Button("⏮", id="prev_button")
                        yield Button("▶", id="play_pause_button")
                        yield Button("⏭", id="next_button")
                        yield Button("🔁", id="loop_button")

                yield Static("Lyrics/Queue Panel (toggleable)", id="lyrics_queue_panel")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        self.bell()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Called when the user clicks a file in the DirectoryTree."""
        self.query_one("#music_name", Label).update(f"Selected: {event.path.name}")


if __name__ == "__main__":
    app = GlyphixApp()
    app.run()
