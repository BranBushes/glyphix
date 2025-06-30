<p align="center">
  <a href="https://github.com/BranBushes/glyphix.git">
    <!-- You can create a simple logo and place it in a .assets directory -->
    <img src="https://raw.githubusercontent.com/your-username/glyphix/main/.assets/logo.png" alt="glyphix logo" width="150">
  </a>
</p>

# glyphix

A modern, powerful, terminal-based music player built with Python and Textual.

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-brightgreen.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-active-success.svg)](https://github.com/your-username/glyphix)

</div>

![A screenshot of the Glyphix music player in action.](https://raw.githubusercontent.com/your-username/glyphix/main/.assets/screenshot.png)

---

## About

`glyphix` is a sophisticated music player that runs directly in your terminal, blending a classic TUI aesthetic with modern features. Designed for audiophiles and keyboard-centric users, `glyphix` provides a fast, efficient, and visually rich way to manage and enjoy your music collection without ever leaving the command line.

## ✨ Features

*   🎵 **High-Fidelity Playback:** Enjoy crisp, clear audio with a robust playback engine that supports all major formats (MP3, FLAC, WAV, OGG, etc.).
*   🖼️ **Album Art in the Terminal:** *(WORK IN PROGRESS)* Automatically extracts and displays embedded album art for the currently playing track.
*   📂 **Multi-Folder Library:** Add multiple music folders to your library and switch between them seamlessly with dedicated tabs.
*   🎤 **Lyrics & Queue Panel:** *(WORK IN PROGRESS)* Toggle between viewing real-time song lyrics (fetched from Genius.com) or managing your upcoming track queue.
*   ⌨️ **Intuitive Controls:** Full playback control with simple, ergonomic keybindings for play, pause, next, previous, and seek.
*   🎨 **Sleek & Responsive UI:** A carefully designed layout that looks great and adapts to your terminal's size.
*   🐧 **Cross-Platform:** Built with Python and Textual, `glyphix` runs on Linux, macOS, and Windows.

## 🚀 Installation

*(WORK IN PROGRESS)*

This project is not yet available as an installable package. Please see the "For Developers" section to run it from the source code.

## 💻 Usage

See the "For Developers" section to learn how to run the application.

Once running, you can use the keybindings below to add music folders and control playback.

## ⌨️ Keybindings

Keybindings are designed for quick and easy access to all features.

### Application & Library Management

| Key           | Action                        |
|---------------|-------------------------------|
| **q**         | Quit the application          |
| **a**         | Add a new music folder tab    |
| **d**         | Close the active folder tab   |
| **l**         | Toggle Lyrics/Queue *(WIP)*   |

### Playback Controls

| Key         | Action                |
|-------------|-----------------------|
| **enter**   | Play selected song    |
| **space**   | Play / Pause          |
| **n**       | Next track            |
| **p**       | Previous track        |
| **s**       | Toggle shuffle *(WIP)*|
| **r**       | Toggle repeat *(WIP)* |

## 🔧 Configuration

*(WORK IN PROGRESS)* A configuration file will allow customization of colors, keybindings, and other settings.

## 🧑‍💻 For Developers

To set up a development environment and run the application:
```bash
# 1. Clone the repository
git clone https://github.com/BranBushes/glyphix.git
cd glyphix

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the required libraries
pip install -r requirements.txt

# 4. Run the application
python3 glyphix.py
```

---

<p align="center">
  Made with ❤️
</p>
