import { describe, expect, it } from "vitest";

import type { ActiveModelsInfo } from "../api/types/provider";
import {
  getCachedActiveModels,
  invalidateActiveModelsCache,
  resetActiveModelsCacheForTests,
  setCachedActiveModels,
} from "./activeModelsCache";

const activeModels: ActiveModelsInfo = {
  resolved_llm: {
    provider_id: "openai",
    model: "gpt-5",
  },
};

describe("activeModelsCache", () => {
  it("returns cached active models until ttl expires", () => {
    resetActiveModelsCacheForTests();

    setCachedActiveModels(activeModels, { now: 1000 });

    expect(getCachedActiveModels({ now: 1000 + 29_999 })).toEqual(activeModels);
    expect(getCachedActiveModels({ now: 1000 + 30_001 })).toBeNull();
  });

  it("invalidates cached active models explicitly", () => {
    resetActiveModelsCacheForTests();

    setCachedActiveModels(activeModels, { now: 1000 });
    invalidateActiveModelsCache();

    expect(getCachedActiveModels({ now: 1001 })).toBeNull();
  });
});
