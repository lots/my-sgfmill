/**
 * Reading positions out of a game: the starting stones and the moves.
 *
 * Mirrors sgfmill.sgf_moves.get_setup_and_moves(), which is what the library
 * uses to turn a game into a board the app can draw.
 */

import { Board } from "./board.js";
import { SgfError } from "./properties.js";

/**
 * Return [board, plays] for a game.
 *
 * The board carries any setup stones, and each play is [colour, point] where
 * point is null for a pass. The main line is followed (the leftmost
 * variation).
 */
export function getSetupAndMoves(game) {
  const size = game.getSize();
  const root = game.getRoot();
  const [black, white, empty] = root.getSetupStones();
  const board = new Board(size);
  board.applySetup(black, white, empty);

  const plays = [];
  for (const node of game.mainLine().slice(1)) {
    const [colour, point] = node.getMove();
    if (colour !== "b" && colour !== "w") continue;
    plays.push([colour, point]);
  }
  return [board, plays];
}

/**
 * Return a board with the first `limit` moves played.
 *
 * Stops early, without raising, if the game contains an illegal move: a file
 * being inspected should still show what it can.
 */
export function positionAfter(game, limit = null) {
  const [start, plays] = getSetupAndMoves(game);
  const count = limit == null ? plays.length : Math.max(0, limit);
  const board = new Board(game.getSize());
  const [black, white, empty] = game.getRoot().getSetupStones();
  board.applySetup(black, white, empty);
  let stopped = false;
  for (const [colour, point] of plays.slice(0, count)) {
    if (point == null) continue;
    try {
      board.play(point[0], point[1], colour);
    } catch (error) {
      stopped = true;
      break;
    }
  }
  return { board, plays: plays.slice(0, count), stopped, start };
}

/**
 * The position a particular node leads to.
 *
 * Unlike positionAfter(), this follows the node's own ancestors rather than
 * the leftmost variation, so clicking a move inside a variation shows that
 * variation's position. Setup stones anywhere along the path are applied as
 * they are met.
 */
export function positionForNode(game, node) {
  const chain = [];
  for (let current = node; current != null; current = current.parent) {
    chain.push(current);
  }
  chain.reverse();                     // root first

  const size = game.getSize();
  const board = new Board(size);
  const [black, white, empty] = chain[0].getSetupStones();
  board.applySetup(black, white, empty);

  let stopped = false;
  for (const sgfNode of chain.slice(1)) {
    const [sblack, swhite, sempty] = sgfNode.getSetupStones();
    if (sblack.length || swhite.length || sempty.length) {
      board.applySetup(sblack, swhite, sempty);
    }
    const [colour, point] = sgfNode.getMove();
    if (point == null) continue;                 // not a move, or a pass
    try {
      board.play(point[0], point[1], colour);
    } catch (error) {
      stopped = true;
      break;
    }
  }
  return { board, stopped };
}

/** Every node of a tree, depth first, in the order the tree pane shows them. */
export function treeNodes(node) {
  const nodes = [node];
  for (const child of node.children) nodes.push(...treeNodes(child));
  return nodes;
}

export { SgfError };
