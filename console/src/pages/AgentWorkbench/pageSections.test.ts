import { describe, expect, it } from "vitest";

import { buildGoalTaskGroups } from "./sections/taskPanels";

describe("pageSections decomposition", () => {
  it("groups parent tasks, standalone tasks, and orphan children via the extracted task panel module", () => {
    const grouped = buildGoalTaskGroups([
      {
        task: { id: "task-parent", parent_task_id: null },
        runtime: null,
      },
      {
        task: { id: "task-child", parent_task_id: "task-parent" },
        runtime: null,
      },
      {
        task: { id: "task-standalone", parent_task_id: null },
        runtime: null,
      },
      {
        task: { id: "task-orphan", parent_task_id: "missing-parent" },
        runtime: null,
      },
    ] as any);

    expect(grouped.groups).toHaveLength(1);
    expect(grouped.groups[0].parent.task.id).toBe("task-parent");
    expect(grouped.groups[0].children.map((item) => item.task.id)).toEqual(["task-child"]);
    expect(grouped.standalone.map((item) => item.task.id)).toEqual(["task-standalone"]);
    expect(grouped.orphanChildren.map((item) => item.task.id)).toEqual(["task-orphan"]);
  });
});
