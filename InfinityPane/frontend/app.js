const { useEffect, useMemo, useRef, useState } = React;

const DEFAULT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const makeId = (prefix) => `${prefix}-${Math.random().toString(36).slice(2, 9)}`;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function App() {
  const canvasRef = useRef(null);
  const [viewport, setViewport] = useState({ x: 0, y: 0, scale: 1 });
  const [tool, setTool] = useState("select");
  const [linkStart, setLinkStart] = useState(null);
  const [status, setStatus] = useState("Ready");

  const [teachers, setTeachers] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [classes, setClasses] = useState([]);
  const [search, setSearch] = useState("");

  const [tables, setTables] = useState([]);
  const [groups, setGroups] = useState([]);
  const [members, setMembers] = useState([]);
  const [edges, setEdges] = useState([]);

  const [dragState, setDragState] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/teachers").then((res) => res.json()),
      fetch("/api/subjects").then((res) => res.json()),
      fetch("/api/classes").then((res) => res.json()),
    ])
      .then(([teacherData, subjectData, classData]) => {
        setTeachers(teacherData);
        setSubjects(subjectData);
        setClasses(classData);
      })
      .catch(() => {
        setTeachers([]);
        setSubjects([]);
        setClasses([]);
      });
  }, []);

  const clientToWorld = (clientX, clientY) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x: (clientX - rect.left) / viewport.scale + viewport.x,
      y: (clientY - rect.top) / viewport.scale + viewport.y,
    };
  };

  useEffect(() => {
    const handleMove = (event) => {
      if (!dragState) return;
      if (dragState.type === "pan") {
        const dx = (event.clientX - dragState.startX) / viewport.scale;
        const dy = (event.clientY - dragState.startY) / viewport.scale;
        setViewport((prev) => ({
          ...prev,
          x: dragState.originX - dx,
          y: dragState.originY - dy,
        }));
        return;
      }

      if (dragState.type === "move-table") {
        const dx = (event.clientX - dragState.startX) / viewport.scale;
        const dy = (event.clientY - dragState.startY) / viewport.scale;
        const nextWorld = {
          x: dragState.originWorldX + dx,
          y: dragState.originWorldY + dy,
        };
        const cursorWorld = clientToWorld(event.clientX, event.clientY);
        const hoverGroup = findDeepestGroupAt(cursorWorld);

        setTables((prev) =>
          prev.map((table) => {
            if (table.id !== dragState.id) return table;
            if (hoverGroup) {
              const parentWorld = getGroupWorldPosition(hoverGroup);
              return {
                ...table,
                parentGroupId: hoverGroup.id,
                x: nextWorld.x - parentWorld.x,
                y: nextWorld.y - parentWorld.y,
              };
            }
            return { ...table, parentGroupId: null, x: nextWorld.x, y: nextWorld.y };
          })
        );

        if (hoverGroup) {
          const padding = 20;
          setGroups((prev) =>
            prev.map((group) => {
              if (group.id !== hoverGroup.id) return group;
              const localX = nextWorld.x - getGroupWorldPosition(group).x;
              const localY = nextWorld.y - getGroupWorldPosition(group).y;
              const safeX = Math.max(padding, localX);
              const safeY = Math.max(padding, localY);
              const tableRef = tables.find((t) => t.id === dragState.id) || dragState.tableSnapshot;
              const tableWidth = tableRef?.width ?? 400;
              const tableHeight = tableRef?.height ?? 220;
              return {
                ...group,
                width: Math.max(group.width, safeX + tableWidth + padding),
                height: Math.max(group.height, safeY + tableHeight + padding),
              };
            })
          );
        }
        return;
      }

      if (dragState.type === "move-group") {
        const dx = (event.clientX - dragState.startX) / viewport.scale;
        const dy = (event.clientY - dragState.startY) / viewport.scale;
        setGroups((prev) =>
          prev.map((group) =>
            group.id === dragState.id
              ? { ...group, x: dragState.originX + dx, y: dragState.originY + dy }
              : group
          )
        );
        return;
      }

      if (dragState.type === "resize-group") {
        const dx = (event.clientX - dragState.startX) / viewport.scale;
        const dy = (event.clientY - dragState.startY) / viewport.scale;
        setGroups((prev) =>
          prev.map((group) =>
            group.id === dragState.id
              ? {
                  ...group,
                  width: clamp(dragState.originW + dx, 120, 800),
                  height: clamp(dragState.originH + dy, 80, 600),
                }
              : group
          )
        );
        return;
      }

      if (dragState.type === "move-member") {
        const dx = (event.clientX - dragState.startX) / viewport.scale;
        const dy = (event.clientY - dragState.startY) / viewport.scale;
        setMembers((prev) =>
          prev.map((member) =>
            member.id === dragState.id
              ? { ...member, x: dragState.originX + dx, y: dragState.originY + dy }
              : member
          )
        );
      }
    };

    const handleUp = () => {
      setDragState(null);
    };

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [dragState, viewport.scale]);

  const filteredTeachers = useMemo(() => {
    if (!search.trim()) return teachers;
    const query = search.toLowerCase();
    return teachers.filter((teacher) =>
      [teacher.name, teacher.id, teacher.subject]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(query))
    );
  }, [teachers, search]);

  const gridStyle = {
    "--grid-size": `${40 * viewport.scale}px`,
    "--grid-offset-x": `${-viewport.x * viewport.scale}px`,
    "--grid-offset-y": `${-viewport.y * viewport.scale}px`,
  };

  const worldStyle = {
    transform: `translate(${-viewport.x * viewport.scale}px, ${-viewport.y * viewport.scale}px) scale(${viewport.scale})`,
  };

  const getTable = (id) => tables.find((table) => table.id === id);

  const getGroup = (id) => groups.find((group) => group.id === id);

  const getTableWorldPosition = (table) => {
    if (!table.parentGroupId) return { x: table.x, y: table.y };
    const parent = getGroup(table.parentGroupId);
    if (!parent) return { x: table.x, y: table.y };
    const parentWorld = getGroupWorldPosition(parent);
    return { x: parentWorld.x + table.x, y: parentWorld.y + table.y };
  };

  const getGroupWorldPosition = (group) => {
    if (!group) return { x: 0, y: 0 };
    if (group.parentType === "root") {
      return { x: group.x, y: group.y };
    }
    if (group.parentType === "table") {
      const table = getTable(group.parentId);
      if (!table) return { x: group.x, y: group.y };
      return { x: table.x + group.x, y: table.y + group.y };
    }
    if (group.parentType === "group") {
      const parent = getGroup(group.parentId);
      const parentWorld = getGroupWorldPosition(parent);
      return { x: parentWorld.x + group.x, y: parentWorld.y + group.y };
    }
    return { x: group.x, y: group.y };
  };

  const getMemberWorldPosition = (member) => {
    if (member.global) return { x: member.x, y: member.y };
    const parent = getGroup(member.parentGroupId);
    const parentWorld = getGroupWorldPosition(parent);
    return { x: parentWorld.x + member.x, y: parentWorld.y + member.y };
  };

  const getGroupBounds = (group) => {
    const world = getGroupWorldPosition(group);
    return {
      x: world.x,
      y: world.y,
      width: group.width,
      height: group.height,
    };
  };

  const findDeepestGroupAt = (point) => {
    const candidates = groups
      .map((group) => ({ group, bounds: getGroupBounds(group) }))
      .filter(({ bounds }) =>
        point.x >= bounds.x &&
        point.x <= bounds.x + bounds.width &&
        point.y >= bounds.y &&
        point.y <= bounds.y + bounds.height
      );

    if (candidates.length === 0) return null;

    const depthOf = (group) => {
      let depth = 0;
      let current = group;
      while (current && current.parentType === "group") {
        depth += 1;
        current = getGroup(current.parentId);
      }
      return depth;
    };

    candidates.sort((a, b) => depthOf(b.group) - depthOf(a.group));
    return candidates[0].group;
  };

  const findTableAt = (point) => {
    return tables.find((table) => {
      const world = getTableWorldPosition(table);
      return (
        point.x >= world.x &&
        point.x <= world.x + table.width &&
        point.y >= world.y &&
        point.y <= world.y + table.height
      );
    });
  };

  const screenToWorld = (event) => clientToWorld(event.clientX, event.clientY);

  const handleWheel = (event) => {
    event.preventDefault();
    setViewport((prev) => {
      const delta = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY;
      const zoomFactor = Math.exp(-delta * 0.0008);
      const nextScale = clamp(prev.scale * zoomFactor, 0.05, 8);
      const rect = canvasRef.current.getBoundingClientRect();
      const mx = (event.clientX - rect.left) / prev.scale + prev.x;
      const my = (event.clientY - rect.top) / prev.scale + prev.y;
      const scaleRatio = nextScale / prev.scale;
      return {
        scale: nextScale,
        x: mx - (mx - prev.x) * scaleRatio,
        y: my - (my - prev.y) * scaleRatio,
      };
    });
  };

  const handleCanvasMouseDown = (event) => {
    if (event.button !== 0) return;
    if (event.target.closest(".node")) return;
    setDragState({
      type: "pan",
      startX: event.clientX,
      startY: event.clientY,
      originX: viewport.x,
      originY: viewport.y,
    });
  };

  const handleDrop = (event) => {
    event.preventDefault();
    const data = event.dataTransfer.getData("application/x-infinitypane");
    if (!data) return;
    const payload = JSON.parse(data);
    const worldPoint = screenToWorld(event);

    const targetGroup = findDeepestGroupAt(worldPoint);
    const targetTable = targetGroup ? null : findTableAt(worldPoint);

    if (payload.type === "teacher") {
      if (targetGroup) {
        const parentWorld = getGroupWorldPosition(targetGroup);
        setMembers((prev) => [
          ...prev,
          {
            id: makeId("teacher"),
            kind: "teacher",
            name: payload.name,
            meta: payload.meta,
            parentGroupId: targetGroup.id,
            global: false,
            x: worldPoint.x - parentWorld.x,
            y: worldPoint.y - parentWorld.y,
          },
        ]);
      } else {
        setMembers((prev) => [
          ...prev,
          {
            id: makeId("teacher"),
            kind: "teacher",
            name: payload.name,
            meta: payload.meta,
            parentGroupId: null,
            global: true,
            x: worldPoint.x,
            y: worldPoint.y,
          },
        ]);
      }
      return;
    }

    if (payload.type === "subject") {
      if (!targetGroup) {
        setStatus("Drop subjects into a group.");
        return;
      }
      const parentWorld = getGroupWorldPosition(targetGroup);
      setMembers((prev) => [
        ...prev,
        {
          id: makeId("subject"),
          kind: "subject",
          name: payload.name,
          meta: payload.meta,
          parentGroupId: targetGroup.id,
          global: false,
          x: worldPoint.x - parentWorld.x,
          y: worldPoint.y - parentWorld.y,
        },
      ]);
      return;
    }

    if (payload.type === "group") {
      const newGroup = {
        id: makeId("group"),
        name: "Group",
        width: 260,
        height: 180,
        parentType: "root",
        parentId: null,
        x: worldPoint.x,
        y: worldPoint.y,
      };
      if (targetGroup) {
        const parentWorld = getGroupWorldPosition(targetGroup);
        newGroup.parentType = "group";
        newGroup.parentId = targetGroup.id;
        newGroup.x = worldPoint.x - parentWorld.x;
        newGroup.y = worldPoint.y - parentWorld.y;
      } else if (targetTable) {
        newGroup.parentType = "table";
        newGroup.parentId = targetTable.id;
        newGroup.x = worldPoint.x - targetTable.x;
        newGroup.y = worldPoint.y - targetTable.y;
      }
      setGroups((prev) => [...prev, newGroup]);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  const createTable = () => {
    const center = {
      x: viewport.x + (canvasRef.current.clientWidth / 2) / viewport.scale,
      y: viewport.y + (canvasRef.current.clientHeight / 2) / viewport.scale,
    };
    setTables((prev) => [
      ...prev,
      {
        id: makeId("table"),
        x: center.x,
        y: center.y,
        parentGroupId: null,
        width: 520,
        height: 280,
        days: DEFAULT_DAYS.slice(0, 6),
        slotsPerDay: 6,
        classId: "",
      },
    ]);
  };

  const createGroup = () => {
    const center = {
      x: viewport.x + (canvasRef.current.clientWidth / 2) / viewport.scale,
      y: viewport.y + (canvasRef.current.clientHeight / 2) / viewport.scale,
    };
    setGroups((prev) => [
      ...prev,
      {
        id: makeId("group"),
        name: "Group",
        width: 260,
        height: 180,
        parentType: "root",
        parentId: null,
        x: center.x,
        y: center.y,
      },
    ]);
  };

  const handleMemberClick = (member) => {
    if (tool !== "arrow") return;
    if (!linkStart) {
      setLinkStart(member);
      setStatus(`Select a ${member.kind === "teacher" ? "subject" : "teacher"} to link.`);
      return;
    }
    if (linkStart.id === member.id) return;

    if (linkStart.kind === member.kind) {
      setStatus("Links must be between a teacher and a subject.");
      setLinkStart(null);
      return;
    }

    const source = linkStart.kind === "subject" ? linkStart : member;
    const target = linkStart.kind === "teacher" ? linkStart : member;

    const targetGroup = getGroup(target.parentGroupId);
    const sourceGroup = getGroup(source.parentGroupId);

    if (!target.global && (!targetGroup || !sourceGroup || targetGroup.id !== sourceGroup.id)) {
      setStatus("Teacher must be in the same group or be global.");
      setLinkStart(null);
      return;
    }

    setEdges((prev) => [
      ...prev,
      {
        id: makeId("edge"),
        sourceId: source.id,
        targetId: target.id,
      },
    ]);
    setLinkStart(null);
    setStatus("Linked.");
  };

  const handleTableContext = (event, table) => {
    event.preventDefault();
    const dayInput = window.prompt(
      "Days (number 4-7 or comma-separated names)",
      table.days.join(",")
    );
    if (dayInput) {
      const trimmed = dayInput.trim();
      let nextDays = table.days;
      if (trimmed.includes(",")) {
        nextDays = trimmed
          .split(",")
          .map((d) => d.trim())
          .filter(Boolean);
      } else {
        const count = parseInt(trimmed, 10);
        if (!Number.isNaN(count)) {
          nextDays = DEFAULT_DAYS.slice(0, clamp(count, 1, DEFAULT_DAYS.length));
        }
      }
      const slotInput = window.prompt("Slots per day", String(table.slotsPerDay));
      const slots = parseInt(slotInput || "", 10);
      setTables((prev) =>
        prev.map((item) =>
          item.id === table.id
            ? {
                ...item,
                days: nextDays,
                slotsPerDay: Number.isNaN(slots) ? item.slotsPerDay : clamp(slots, 1, 12),
                width: Math.max(400, nextDays.length * 80),
                height: Math.max(220, (Number.isNaN(slots) ? item.slotsPerDay : slots) * 26 + 80),
              }
            : item
        )
      );
    }
  };

  const tableHasGroup = (tableId) => {
    const tableGroups = groups.filter((group) => group.parentType === "table" && group.parentId === tableId);
    if (tableGroups.length) return true;
    const hasNested = groups.some((group) => {
      if (group.parentType !== "group") return false;
      let current = group;
      while (current && current.parentType === "group") {
        const parent = getGroup(current.parentId);
        if (!parent) break;
        if (parent.parentType === "table" && parent.parentId === tableId) return true;
        current = parent;
      }
      return false;
    });
    return hasNested;
  };

  const renderTableGrid = (table) => {
    const rows = Array.from({ length: table.slotsPerDay }, (_, i) => i + 1);
    return (
      <div
        className="table-grid"
        style={{ gridTemplateColumns: `repeat(${table.days.length}, minmax(60px, 1fr))` }}
      >
        {table.days.map((day) => (
          <div key={`day-${day}`} className="cell">
            {day}
          </div>
        ))}
        {rows.flatMap((row) =>
          table.days.map((day) => (
            <div key={`${day}-${row}`} className="cell">
              {row}
            </div>
          ))
        )}
      </div>
    );
  };

  const edgeLines = edges
    .map((edge) => {
      const source = members.find((member) => member.id === edge.sourceId);
      const target = members.find((member) => member.id === edge.targetId);
      if (!source || !target) return null;
      const sourceWorld = getMemberWorldPosition(source);
      const targetWorld = getMemberWorldPosition(target);
      const anchorX = 70;
      const anchorY = 16;
      return {
        id: edge.id,
        sx: sourceWorld.x + anchorX,
        sy: sourceWorld.y + anchorY,
        tx: targetWorld.x + anchorX,
        ty: targetWorld.y + anchorY,
      };
    })
    .filter(Boolean);

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>Teachers</h2>
        <input
          className="search-input"
          placeholder="Search by name, id, subject"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        {filteredTeachers.map((teacher) => (
          <div
            key={teacher.id}
            className="list-item"
            draggable
            onDragStart={(event) => {
              event.dataTransfer.setData(
                "application/x-infinitypane",
                JSON.stringify({
                  type: "teacher",
                  name: teacher.name,
                  meta: teacher,
                })
              );
            }}
          >
            {teacher.name}
            <small>
              {teacher.id} • {teacher.subject}
            </small>
          </div>
        ))}
      </aside>

      <main className="canvas-wrapper">
        <div className="toolbar">
          <button className="tool-button" onClick={createTable}>Table</button>
          <button className="tool-button" onClick={createGroup}>Group</button>
          <button
            className={`tool-button ${tool === "arrow" ? "active" : ""}`}
            onClick={() => {
              setTool(tool === "arrow" ? "select" : "arrow");
              setLinkStart(null);
            }}
          >
            Arrow
          </button>
        </div>

        <div
          ref={canvasRef}
          className="canvas"
          style={gridStyle}
          onWheel={handleWheel}
          onMouseDown={handleCanvasMouseDown}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          <div className="world" style={worldStyle}>
            <svg className="edge-layer">
              <defs>
                <marker
                  id="arrowhead"
                  markerWidth="10"
                  markerHeight="7"
                  refX="10"
                  refY="3.5"
                  orient="auto"
                >
                  <polygon points="0 0, 10 3.5, 0 7" fill="#8aa3ff" />
                </marker>
              </defs>
              {edgeLines.map((line) => (
                <path
                  key={line.id}
                  className="edge-line"
                  markerEnd="url(#arrowhead)"
                  d={`M ${line.sx} ${line.sy} L ${line.tx} ${line.ty}`}
                />
              ))}
            </svg>
            {groups.map((group) => {
              const world = getGroupWorldPosition(group);
              return (
                <div
                  key={group.id}
                  className="node group-node"
                  style={{ left: world.x, top: world.y, width: group.width, height: group.height }}
                >
                  <div
                    className="node-header"
                    onMouseDown={(event) => {
                      event.stopPropagation();
                      setDragState({
                        type: "move-group",
                        id: group.id,
                        startX: event.clientX,
                        startY: event.clientY,
                        originX: group.x,
                        originY: group.y,
                      });
                    }}
                  >
                    <input
                      className="group-name"
                      value={group.name}
                      onChange={(event) => {
                        const value = event.target.value;
                        setGroups((prev) =>
                          prev.map((item) => (item.id === group.id ? { ...item, name: value } : item))
                        );
                      }}
                    />
                    <span>Group</span>
                  </div>
                  <div className="group-resizer"
                    onMouseDown={(event) => {
                      event.stopPropagation();
                      setDragState({
                        type: "resize-group",
                        id: group.id,
                        startX: event.clientX,
                        startY: event.clientY,
                        originW: group.width,
                        originH: group.height,
                      });
                    }}
                  />
                </div>
              );
            })}

            {tables.map((table) => {
              const world = getTableWorldPosition(table);
              return (
                <div
                  key={table.id}
                  className="node"
                  style={{ left: world.x, top: world.y, width: table.width, height: table.height }}
                  onContextMenu={(event) => handleTableContext(event, table)}
                >
                  <div
                    className="node-header"
                    onMouseDown={(event) => {
                      event.stopPropagation();
                      const worldPos = getTableWorldPosition(table);
                      setDragState({
                        type: "move-table",
                        id: table.id,
                        startX: event.clientX,
                        startY: event.clientY,
                        originX: table.x,
                        originY: table.y,
                        originWorldX: worldPos.x,
                        originWorldY: worldPos.y,
                        tableSnapshot: { width: table.width, height: table.height },
                      });
                    }}
                  >
                    <span>Timetable</span>
                    <select
                      value={table.classId}
                      onChange={(event) => {
                        const value = event.target.value;
                        setTables((prev) =>
                          prev.map((item) =>
                            item.id === table.id ? { ...item, classId: value } : item
                          )
                        );
                      }}
                    >
                      <option value="">Select class</option>
                      {classes.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="table-body">
                    {renderTableGrid(table)}
                    {!table.classId && (
                      <div className="table-warning">Link this table to a class.</div>
                    )}
                    {!tableHasGroup(table.id) && (
                      <div className="table-warning">Each table needs at least one group.</div>
                    )}
                    <div className="table-warning">Right-click to edit days and time slots.</div>
                  </div>
                </div>
              );
            })}

            {members.map((member) => {
              const world = getMemberWorldPosition(member);
              return (
                <div
                  key={member.id}
                  className={`member ${member.kind}`}
                  style={{ left: world.x, top: world.y, position: "absolute" }}
                  onClick={() => handleMemberClick(member)}
                  onMouseDown={(event) => {
                    event.stopPropagation();
                    setDragState({
                      type: "move-member",
                      id: member.id,
                      startX: event.clientX,
                      startY: event.clientY,
                      originX: member.x,
                      originY: member.y,
                    });
                  }}
                >
                  <strong>{member.name}</strong>
                  <small>
                    {member.kind === "teacher" ? "Teacher" : "Subject"}
                    {member.global ? " • Global" : ""}
                  </small>
                </div>
              );
            })}
          </div>
        </div>

        <div className="status-bar">
          {tool === "arrow"
            ? linkStart
              ? `Arrow tool: linking from ${linkStart.name}`
              : "Arrow tool: select a subject or teacher"
            : "Pan: drag empty space • Zoom: mouse wheel"}
        </div>
      </main>

      <aside className="sidebar right">
        <h2>Subjects</h2>
        {subjects.map((subject) => (
          <div
            key={subject.id}
            className="list-item"
            draggable
            onDragStart={(event) => {
              event.dataTransfer.setData(
                "application/x-infinitypane",
                JSON.stringify({
                  type: "subject",
                  name: subject.name,
                  meta: subject,
                })
              );
            }}
          >
            {subject.name}
            <small>{subject.id}</small>
          </div>
        ))}
        <h2>Quick Add</h2>
        <div
          className="list-item"
          draggable
          onDragStart={(event) => {
            event.dataTransfer.setData(
              "application/x-infinitypane",
              JSON.stringify({ type: "group" })
            );
          }}
        >
          Drag Group Block
          <small>Drop into table or group</small>
        </div>
      </aside>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
