import { describe, it, expect } from "vitest";
import { stagger, fadeUp } from "./animations";

describe("animation variants", () => {
  it("stagger has hidden and show states", () => {
    expect(stagger).toHaveProperty("hidden");
    expect(stagger).toHaveProperty("show");
    expect(stagger.hidden).toEqual({ opacity: 0 });
  });

  it("stagger.show includes staggerChildren", () => {
    const show = stagger.show as { opacity: number; transition: { staggerChildren: number } };
    expect(show.opacity).toBe(1);
    expect(show.transition.staggerChildren).toBe(0.08);
  });

  it("fadeUp has hidden and show states", () => {
    expect(fadeUp).toHaveProperty("hidden");
    expect(fadeUp).toHaveProperty("show");
    expect(fadeUp.hidden).toEqual({ opacity: 0, y: 16 });
  });

  it("fadeUp.show animates opacity and y", () => {
    const show = fadeUp.show as { opacity: number; y: number; transition: { duration: number } };
    expect(show.opacity).toBe(1);
    expect(show.y).toBe(0);
    expect(show.transition.duration).toBe(0.4);
  });
});
