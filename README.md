# qsvgchess

A feature-rich, modern chess application built with Python and PyQt5, featuring high-quality SVG graphics, engine analysis, and an interactive PGN browser.

![Chessboard](icon.png)

## Features

- **High-Quality SVG Chessboard**: Crisp, responsive visuals using SVG rendering. Supports drag-and-drop piece movement and smooth animations.
- **Engine Analysis**: Built-in support for UCI chess engines (like Stockfish). Features a real-time evaluation bar, depth tracking, and best-line visualization.
- **Advanced PGN Browser**: 
  - Load and save PGN files.
  - Interactive move navigation with variation support.
  - HTML-styled move list with Light and Dark themes.
  - Add and edit comments directly on moves.
- **Puzzle Trainer**: A dedicated mode for practicing chess puzzles.
  - Free and Timed modes.
  - Hint system and move validation.
  - Session statistics and performance summaries.
- **Intuitive UI/UX**:
  - Modern Dark Theme (custom QSS).
  - Legal move highlighting (dots/circles).
  - Elegant pawn promotion dialog with graphical icons.
  - Board flipping and layout customization.
  - Splash screen for a polished startup experience.

## Installation

### Prerequisites

- Python 3.8+
- [Stockfish](https://stockfishchess.org/download/) (or any UCI-compatible engine) installed and available in your PATH.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/alexanderortizcuellar/qchess.git
   cd qchess
   ```

2. Install the required Python dependencies:
   ```bash
   pip install PyQt5 chess
   ```

## How to Run

Launch the application by running the `main.py` script:

```bash
python main.py
```

## Project Structure

- `main.py`: Entry point of the application, handles startup and styling.
- `chessapp.py`: Main application window and core orchestration logic.
- `chessboard.py`: Interactive SVG-based chessboard component.
- `engine.py`: UCI engine wrapper for analysis and evaluation.
- `movemanager.py`: Logic for managing game history, PGNs, and variations.
- `puzzles.py`: Puzzle training module and UI.
- `pgn_browser.py`: Rich text display for move history.
- `bar.py`: Visual evaluation bar for engine scores.
- `style.qss`: Custom stylesheet for the modern dark interface.

## Technical Stack

- **Language**: Python
- **GUI Framework**: [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- **Chess Logic**: [chess](https://github.com/niklasf/python-chess)
- **Graphics**: SVG via `QtSvg`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
