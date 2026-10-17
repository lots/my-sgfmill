/**
 * A Go board: stones, captures and the checks sgfmill's Board makes.
 *
 * sgfmill's Board.play() raises ValueError for an occupied point or a point
 * with no liberties (a suicide), and the app treats that as "stop replaying".
 */

import { SgfError } from "./properties.js";

export class Board {
  constructor(size) {
    this.size = size;
    // board[row][col] is "b", "w" or null. Row 0 is the bottom.
    this.board = Array.from({ length: size }, () => new Array(size).fill(null));
  }

  get(row, col) {
    return this.board[row][col];
  }

  listStones(colour) {
    const stones = [];
    for (let row = 0; row < this.size; row++) {
      for (let col = 0; col < this.size; col++) {
        if (this.board[row][col] === colour) stones.push([row, col]);
      }
    }
    return stones;
  }

  applySetup(black = [], white = [], empty = []) {
    for (const [row, col] of black) this.board[row][col] = "b";
    for (const [row, col] of white) this.board[row][col] = "w";
    for (const [row, col] of empty) this.board[row][col] = null;
  }

  /** Play a stone, removing any captured groups. Throws on an illegal move. */
  play(row, col, colour) {
    if (row < 0 || row >= this.size || col < 0 || col >= this.size) {
      throw new SgfError("point off the board");
    }
    if (this.board[row][col] != null) throw new SgfError("point is occupied");
    this.board[row][col] = colour;
    const opponent = colour === "b" ? "w" : "b";
    for (const [r, c] of this.neighbours(row, col)) {
      if (this.board[r][c] === opponent) {
        const group = this.chain(r, c);
        if (this.countLiberties(group) === 0) {
          for (const [gr, gc] of group) this.board[gr][gc] = null;
        }
      }
    }
    if (this.countLiberties(this.chain(row, col)) === 0) {
      // Suicide: undo the stone before complaining, as nothing moved.
      this.board[row][col] = null;
      throw new SgfError("suicide");
    }
  }

  neighbours(row, col) {
    const result = [];
    if (row > 0) result.push([row - 1, col]);
    if (row < this.size - 1) result.push([row + 1, col]);
    if (col > 0) result.push([row, col - 1]);
    if (col < this.size - 1) result.push([row, col + 1]);
    return result;
  }

  /** The connected stones of the same colour containing this point. */
  chain(row, col) {
    const colour = this.board[row][col];
    if (colour == null) return [];
    const seen = new Set();
    const stack = [[row, col]];
    const group = [];
    seen.add(row * this.size + col);
    while (stack.length > 0) {
      const [r, c] = stack.pop();
      group.push([r, c]);
      for (const [nr, nc] of this.neighbours(r, c)) {
        const key = nr * this.size + nc;
        if (seen.has(key)) continue;
        if (this.board[nr][nc] === colour) {
          seen.add(key);
          stack.push([nr, nc]);
        }
      }
    }
    return group;
  }

  countLiberties(group) {
    const liberties = new Set();
    for (const [row, col] of group) {
      for (const [nr, nc] of this.neighbours(row, col)) {
        if (this.board[nr][nc] == null) liberties.add(nr * this.size + nc);
      }
    }
    return liberties.size;
  }
}

/**
 * A board diagram, drawn as text.
 *
 * The layout is sgfmill.ascii_boards.render_board's, character for character:
 * row numbers down the side (right aligned), column letters along the bottom
 * skipping I, '#' for black and 'o' for white. The differential tests compare
 * this with the Python renderer, so the two front ends show the same diagram.
 */
export function renderBoard(board) {
  const size = board.size;
  const gutter = String(size).length;
  const lines = [];
  for (let row = size - 1; row >= 0; row--) {
    const cells = [];
    for (let col = 0; col < size; col++) {
      const stone = board.board[row][col];
      cells.push(stone === "b" ? "#" : stone === "w" ? "o" : ".");
    }
    lines.push(String(row + 1).padStart(gutter, " ") + "  " +
               cells.join("  "));
  }
  const letters = [];
  for (let col = 0; col < size; col++) {
    letters.push(col < 8
      ? String.fromCharCode(65 + col)
      : String.fromCharCode(66 + col));
  }
  lines.push(" ".repeat(gutter + 2) + letters.join("  "));
  return lines.join("\n");
}
