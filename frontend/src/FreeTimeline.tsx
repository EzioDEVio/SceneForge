import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  api,
  type Project,
  type Finishing,
  type TimelineLayerClip,
  type ProjectAudioClip,
} from "./api";
import { sequenceClips } from "./ProjectTimeline";
import {
  LayerPreview,
  LAYER_TIME,
  type LayerActions,
  ADD_TEXT,
} from "./TimelineLayers";
import { ASSET_DRAG_TYPE, collectDroppedFiles } from "./timelineDrop";
import { AssetWave } from "./NarrationWave";
import { TEXT_TOOL_DRAG } from "./TimelineLayers";

type Item = {
  key: string;
  kind: "scene" | "layer" | "audio";
  id: string;
  start: number;
  duration: number;
  row: number;
  label: string;
};
const lanes = 12,
  rowH = 52;
export function freeItems(p: Project): Item[] {
  return [
    ...(p.finishing_json?.free_timeline?.clips || []).map((c) => ({
      key: "scene:" + c.id,
      kind: "scene" as const,
      id: c.id,
      start: c.start_ms,
      duration: c.duration_ms,
      row: c.track,
      label:
        p.scenes.find((s) => s.id === c.scene_id)?.title || "Missing scene",
    })),
    ...(p.finishing_json?.layer_clips || []).map((c) => ({
      key: "layer:" + c.id,
      kind: "layer" as const,
      id: c.id,
      start: c.start_ms,
      duration: c.duration_ms,
      row: c.track,
      label: c.name || c.text || c.kind,
    })),
    ...(p.finishing_json?.audio_clips || []).map((c) => ({
      key: "audio:" + c.id,
      kind: "audio" as const,
      id: c.id,
      start: c.start_ms,
      duration: c.source_out_ms - c.source_in_ms,
      row: 6 + Math.max(0, Math.min(5, Number((c.track || "A3").slice(1)) - 3)),
      label: c.name || "Audio",
    })),
  ];
}
export function seedFree(p: Project) {
  return {
    enabled: true,
    clips: sequenceClips(p.scenes)
      .filter((c) => c.scene.shots.length)
      .map((c) => ({
        id: crypto.randomUUID(),
        scene_id: c.scene.id,
        start_ms: Math.round(c.start),
        source_in_ms: 0,
        duration_ms: Math.round(c.duration),
        track: 5,
      })),
  };
}
export function moveFree(
  p: Project,
  keys: string[],
  delta: number,
  rows: number,
): Partial<Finishing> {
  const items = freeItems(p).filter((c) => keys.includes(c.key));
  if (!items.length) return {};
  delta = Math.max(-Math.min(...items.map((c) => c.start)), delta);
  // Pictures stay in picture lanes, sound in audio lanes. Shared row delta preserves ordering.
  rows = Math.max(
    Math.max(...items.map((c) => (c.kind === "audio" ? 6 : 0) - c.row)),
    Math.min(
      Math.min(...items.map((c) => (c.kind === "audio" ? 11 : 5) - c.row)),
      rows,
    ),
  );
  return {
    free_timeline: {
      enabled: true,
      clips: (p.finishing_json?.free_timeline?.clips || []).map((c) =>
        keys.includes("scene:" + c.id)
          ? { ...c, start_ms: c.start_ms + delta, track: c.track + rows }
          : c,
      ),
    },
    layer_clips: (p.finishing_json?.layer_clips || []).map((c) =>
      keys.includes("layer:" + c.id)
        ? { ...c, start_ms: c.start_ms + delta, track: c.track + rows }
        : c,
    ),
    audio_clips: (p.finishing_json?.audio_clips || []).map((c) =>
      keys.includes("audio:" + c.id)
        ? {
            ...c,
            start_ms: c.start_ms + delta,
            track: ("A" +
              (Number((c.track || "A3").slice(1)) +
                rows)) as ProjectAudioClip["track"],
          }
        : c,
    ),
  };
}
export function cutFreeRange(p: Project, keys: string[], a: number, b: number) {
  const fin = p.finishing_json || {},
    selected: string[] = [];
  function cut(c: any, kind: "scene" | "layer" | "audio") {
    const duration =
      kind === "audio" ? c.source_out_ms - c.source_in_ms : c.duration_ms;
    if (
      !keys.includes(kind + ":" + c.id) ||
      b <= c.start_ms ||
      a >= c.start_ms + duration
    )
      return [c];
    const cuts = [
      ...new Set([
        0,
        Math.max(0, a - c.start_ms),
        Math.min(duration, b - c.start_ms),
        duration,
      ]),
    ].sort((x, y) => x - y);
    return cuts.slice(0, -1).map((from, i) => {
      const to = cuts[i + 1],
        n = to - from;
      if (n < 100)
        throw Error(
          "Keep the highlighted range and remaining edges at least 0.1 seconds long.",
        );
      const id = cuts.length === 2 ? c.id : crypto.randomUUID(),
        next = { ...c, id, start_ms: c.start_ms + from };
      if (kind === "audio") {
        next.source_in_ms = c.source_in_ms + from;
        next.source_out_ms = c.source_in_ms + to;
        if (from) next.fade_in_ms = 0;
        if (to < duration) next.fade_out_ms = 0;
      } else {
        next.duration_ms = n;
        if (kind === "scene" || c.kind === "video")
          next.source_in_ms = (c.source_in_ms || 0) + from;
      }
      if (next.start_ms >= a && next.start_ms + n <= b)
        selected.push(kind + ":" + id);
      return next;
    });
  }
  return {
    patch: {
      free_timeline: {
        enabled: true,
        clips: (fin.free_timeline?.clips || []).flatMap((c) => cut(c, "scene")),
      },
      layer_clips: (fin.layer_clips || []).flatMap((c) => cut(c, "layer")),
      audio_clips: (fin.audio_clips || []).flatMap((c) => cut(c, "audio")),
    } as Partial<Finishing>,
    selected,
  };
}
/** Snap once, then use that same cut for eligibility and every source offset. */
export function splitFreeAt(p: Project, keys: string[], time: number) {
  const cut = Math.round(Math.round(time * p.fps / 1000) * 1000 / p.fps);
  const eligible = freeItems(p).filter(c => (!keys.length || keys.includes(c.key)) && cut - c.start >= 100 && c.start + c.duration - cut >= 100);
  if (!eligible.length) throw Error(keys.length
    ? "The playhead must be inside a selected clip, at least 0.1 seconds from either edge. Select the clip under the playhead, or clear selection to cut all clips there."
    : "Move the playhead inside a clip, at least 0.1 seconds from either edge.");
  const ids = new Set(eligible.map(c => c.key)), selected: string[] = [];
  function split(c: any, kind: "scene" | "layer" | "audio") {
    if (!ids.has(kind + ":" + c.id)) return [c];
    const n = cut - c.start_ms, id = crypto.randomUUID();
    const left = {...c}, right = {...c, id, start_ms: cut};
    if (kind === "audio") {
      left.source_out_ms = c.source_in_ms + n; left.fade_out_ms = 0;
      right.source_in_ms = c.source_in_ms + n; right.fade_in_ms = 0;
    } else {
      left.duration_ms = n; right.duration_ms = c.duration_ms - n;
      if (kind === "scene" || c.kind === "video") right.source_in_ms = (c.source_in_ms || 0) + n;
    }
    selected.push(kind + ":" + id);
    return [left, right];
  }
  const fin = p.finishing_json || {};
  return {count: eligible.length, selected, patch: {
    free_timeline: {enabled: true, clips: (fin.free_timeline?.clips || []).flatMap(c => split(c, "scene"))},
    layer_clips: (fin.layer_clips || []).flatMap(c => split(c, "layer")),
    audio_clips: (fin.audio_clips || []).flatMap(c => split(c, "audio")),
  } as Partial<Finishing>};
}
export function FreeTimeline({
  project,
  disabled,
  onEdit,
  onSelectScene,
  layerActions,
  onSelectAudio,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  onExport,
  onRefresh,
  onViewSources,
}: {
  project: Project;
  disabled: boolean;
  onEdit: (patch: Partial<Finishing>, label: string) => Promise<boolean>;
  onSelectScene: (id: string) => void;
  layerActions: LayerActions;
  onSelectAudio: (id: string) => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onExport: () => void;
  onRefresh: () => Promise<unknown>;
  onViewSources: () => void;
}) {
  const [selected, setSelected] = useState<string[]>([]),
    [expanded, setExpanded] = useState(false),
    [minimized, setMinimized] = useState(false),
    [height, setHeight] = useState(() => {try {const h = Number(localStorage.getItem(`sceneforge.freeHeight.${project.id}`));return h >= 240 ? h : 360;}catch {return 360;}}),
    [viewport, setViewport] = useState(window.innerHeight),
    [boxMode, setBoxMode] = useState(false),
    [rangeMode, setRangeMode] = useState(false),
    [range, setRange] = useState<{ a: number; b: number } | null>(null),
    [box, setBox] = useState<any>(null),
    [moving, setMoving] = useState<Partial<Finishing> | null>(null),
    [time, setTime] = useState(0),
    [scale, setScale] = useState(70),
    [snap, setSnap] = useState(true),
    [playing, setPlaying] = useState(false),
    [preview, setPreview] = useState(false),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [rendering, setRendering] = useState("");
  const canvas = useRef<HTMLDivElement>(null),
    gesture = useRef<any>(null),
    last = useRef(moving),
    selectedRef = useRef(selected),
    cancel = useRef(false),
    job = useRef<string | null>(null);
  const saving = useRef(false);
  const resizeDrag = useRef<{y:number; height:number} | null>(null);
  const maxHeight = Math.max(240, viewport - 160);
  const viewHeight = minimized ? 76 : expanded ? maxHeight : Math.max(240, Math.min(maxHeight, height));
  useEffect(() => {const resize = () => setViewport(window.innerHeight);window.addEventListener("resize", resize);return () => window.removeEventListener("resize", resize);}, []);
  useEffect(() => {try {localStorage.setItem(`sceneforge.freeHeight.${project.id}`, String(height));}catch {}}, [height, project.id]);
  last.current = moving;
  selectedRef.current = selected;
  const current = {
      ...project,
      finishing_json: { ...project.finishing_json, ...moving },
    },
    items = freeItems(current),
    length = Math.max(1000, ...items.map((c) => c.start + c.duration)),
    width = Math.max(1200, ((length + 15000) / 1000) * scale),
    frame = 1000 / project.fps;
  useEffect(() => {
    const id = requestAnimationFrame(() =>
      canvas.current
        ?.querySelector<HTMLElement>(".free-scene")
        ?.scrollIntoView({ block: "nearest" }),
    );
    return () => cancelAnimationFrame(id);
  }, [project.id]);
  useEffect(() => {
    cancel.current = false;
    return () => {
      cancel.current = true;
      if (job.current) void api.cancelJob(job.current).catch(() => {});
    };
  }, [project.id]);
  useEffect(() => {
    window.dispatchEvent(new CustomEvent(LAYER_TIME, { detail: time }));
    const add = (e: Event) => {
      if (!disabled && !pending)
        layerActions.onAdd((e as CustomEvent).detail, Math.round(time), 0);
    };
    window.addEventListener(ADD_TEXT, add);
    return () => window.removeEventListener(ADD_TEXT, add);
  }, [time, disabled, pending]);
  useEffect(() => {
    if (!playing) return;
    let raf = 0,
      start = performance.now(),
      from = time;
    const tick = () => {
      const next = from + performance.now() - start;
      if (next >= length) {
        setTime(length);
        setPlaying(false);
        return;
      }
      setTime(next);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, length]);
  function thumbnail(item: Item) {
    if (item.kind === "audio") return undefined;
    if (item.kind === "scene") {
      const clip = project.finishing_json?.free_timeline?.clips.find(
          (c) => c.id === item.id,
        ),
        scene = project.scenes.find((s) => s.id === clip?.scene_id),
        shot = scene?.shots[0];
      return shot
        ? api.assetThumbUrl(
            shot.asset_id,
            160,
            (shot.source_in_ms || 0) + (clip?.source_in_ms || 0),
          )
        : undefined;
    }
    const clip = project.finishing_json?.layer_clips?.find(
      (c) => c.id === item.id,
    );
    return clip?.asset_id
      ? api.assetThumbUrl(clip.asset_id, 160, clip.source_in_ms || 0)
      : undefined;
  }
  function choose(item: Item) {
    if (item.kind === "scene") {
      const c = project.finishing_json?.free_timeline?.clips.find(
        (c) => c.id === item.id,
      );
      if (c) onSelectScene(c.scene_id);
    } else if (item.kind === "layer") layerActions.onSelect(item.id);
    else {
      layerActions.onSelect("");
      onSelectAudio(item.id);
      const sceneId = project.scenes[0]?.id;
      if (sceneId) {
        onSelectScene(sceneId);
        setTimeout(
          () =>
            window.dispatchEvent(
              new CustomEvent("sceneforge-open-tab", {
                detail: { sceneId, tab: "Audio" },
              }),
            ),
          0,
        );
      }
    }
  }
  async function save(patch: Partial<Finishing>, label: string) {
    if (saving.current) return false;
    saving.current = true;
    setPending(true);
    setError("");
    try {
      const ok = await onEdit(patch, label);
      if (!ok)
        setError(
          "The change could not be saved. Your previous placement is kept.",
        );
      return ok;
    } catch (e: any) {
      setError(e.message);
      return false;
    } finally {
      saving.current = false;
      setPending(false);
      setMoving(null);
    }
  }
  async function split() {
    if (disabled || saving.current) return;
    try {
      const result = splitFreeAt(project, selectedRef.current, time);
      setPlaying(false);
      if (await save(result.patch, "split free timeline selection")) {
        setSelected(result.selected);
        setError(`Split ${result.count} clip${result.count === 1 ? "" : "s"}. The right pieces are selected for your next cut. Source scenes stay intact.`);
      }
    } catch (e: any) { setError(e.message); }
  }
  function remove() {
    void save(
      {
        free_timeline: {
          enabled: true,
          clips: project.finishing_json!.free_timeline!.clips.filter(
            (c) => !selected.includes("scene:" + c.id),
          ),
        },
        layer_clips: (project.finishing_json?.layer_clips || []).filter(
          (c) => !selected.includes("layer:" + c.id),
        ),
        audio_clips: (project.finishing_json?.audio_clips || []).filter(
          (c) => !selected.includes("audio:" + c.id),
        ),
      },
      "remove free timeline clips",
    );
    setSelected([]);
  }
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (
        (e.target as HTMLElement)?.closest(
          "input,textarea,select,[contenteditable]",
        ) ||
        document.querySelector('[role="dialog"],dialog[open]')
      )
        return;
      if (e.key === "Escape") {
        if (gesture.current?.previous) setSelected(gesture.current.previous);
        gesture.current = null;
        setRange(null);
        setRangeMode(false);
        setBox(null);
        setMoving(null);
        setBoxMode(false);
      }
      if (disabled || pending) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        e.shiftKey ? onRedo() : onUndo();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        onRedo();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
        e.preventDefault();
        setSelected(freeItems(project).map((c) => c.key));
      } else if (e.key === "Delete" && selectedRef.current.length) {
        e.preventDefault();
        remove();
      } else if (e.key.toLowerCase() === "s") {
        e.preventDefault();
        split();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [project, time, disabled, pending]);
  async function drop(e: React.DragEvent, row: number) {
    e.preventDefault();
    if (disabled || pending) return;
    const rect = e.currentTarget.getBoundingClientRect(),
      ms = Math.max(
        0,
        Math.round((((e.clientX - rect.left) / scale) * 1000) / frame) * frame,
      ),
      kind = e.dataTransfer.getData(TEXT_TOOL_DRAG);
    if (kind && row < 6) {
      layerActions.onAdd(kind as any, Math.round(ms), row);
      return;
    }
    if (saving.current) return false;
    saving.current = true;
    setPending(true);
    setError("");
    try {
      let assets: any[] = [];
      const files = await collectDroppedFiles(e.dataTransfer);
      if (files.length) {
        for (const f of files)
          assets.push(await api.uploadAsset(project.id, f));
      } else {
        const raw = e.dataTransfer.getData(ASSET_DRAG_TYPE);
        const ids = JSON.parse(raw || "[]");
        const pool = await api.listAssets(project.id);
        assets = pool.filter((a) =>
          (Array.isArray(ids) ? ids : [ids]).some(
            (id: any) => id === a.id || id?.id === a.id,
          ),
        );
      }
      const layers = [...(project.finishing_json?.layer_clips || [])],
        audio = [...(project.finishing_json?.audio_clips || [])];
      for (const a of assets) {
        if (a.type === "audio") {
          if (row < 6) throw Error("Drop audio on an audio lane.");
          audio.push({
            id: crypto.randomUUID(),
            asset_id: a.id,
            name: a.original_filename,
            start_ms: Math.round(ms),
            source_in_ms: 0,
            source_out_ms: a.duration_ms,
            volume: 100,
            fade_in_ms: 0,
            fade_out_ms: 0,
            track: "A" + (row - 3),
          } as ProjectAudioClip);
        } else {
          if (row >= 6) throw Error("Drop pictures on a picture lane.");
          layers.push({
            id: crypto.randomUUID(),
            kind: a.type,
            name: a.original_filename,
            asset_id: a.id,
            start_ms: Math.round(ms),
            duration_ms: a.type === "video" ? a.duration_ms : 4000,
            track: row,
            x: 50,
            y: 50,
            width: 100,
            rotation: 0,
            opacity: 100,
            size: 72,
            color: "#ffffff",
            family: "Noto Sans",
            align: "center",
            ...(a.type === "video"
              ? { source_in_ms: 0, mute: false, volume: 100 }
              : {}),
          });
        }
      }
      if (assets.length)
        await onEdit(
          { layer_clips: layers, audio_clips: audio },
          "drop media on free timeline",
        );
    } catch (e: any) {
      setError(e.message);
    } finally {
      saving.current = false;
      setPending(false);
    }
  }
  async function renderMissing() {
    setPending(true);
    cancel.current = false;
    setError("");
    try {
      for (const id of [
        ...new Set(
          project.finishing_json?.free_timeline?.clips.map((c) => c.scene_id),
        ),
      ]) {
        const s = project.scenes.find((s) => s.id === id);
        if (!s || !s.shots.length)
          throw Error("A placed source scene needs media.");
        if (s.rendered_asset_id && !s.is_stale) continue;
        setRendering("Rendering " + s.title);
        job.current = (await api.renderPart(id)).job_id;
        while (!cancel.current) {
          const j = await api.getJob(job.current);
          if (j.status === "succeeded") break;
          if (["failed", "cancelled"].includes(j.status))
            throw Error(j.error || "Render stopped");
          await new Promise((r) => setTimeout(r, 350));
        }
        if (cancel.current) break;
        job.current = null;
        await onRefresh();
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRendering("");
      setPending(false);
      job.current = null;
    }
  }
  const host = document.getElementById("sequence-viewer");
  return (
    <section
      className={`free-timeline ${minimized ? "minimized" : ""}`}
      style={{height: viewHeight}}
      aria-label="Free timeline editor"
    >
      <div className="free-resizer" role="separator" aria-label="Resize free timeline" aria-orientation="horizontal" aria-valuemin={240} aria-valuemax={maxHeight} aria-valuenow={minimized ? 240 : viewHeight} aria-valuetext={minimized ? "Minimized" : `${Math.round(viewHeight)} pixels`} tabIndex={0}
        title="Drag up or down to resize. Arrow Up/Down changes height; Home/End sets smallest/largest."
        onPointerDown={e => {if(e.button !== 0)return;e.preventDefault();resizeDrag.current={y:e.clientY,height:minimized?Math.max(240,Math.min(maxHeight,height)):viewHeight};setMinimized(false);setExpanded(false);e.currentTarget.setPointerCapture(e.pointerId);}}
        onPointerMove={e => {const g=resizeDrag.current;if(g&&e.currentTarget.hasPointerCapture(e.pointerId))setHeight(Math.round(Math.max(240,Math.min(maxHeight,g.height+g.y-e.clientY))));}}
        onPointerUp={e => {resizeDrag.current=null;if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);}}
        onLostPointerCapture={() => {resizeDrag.current=null;}}
        onPointerCancel={() => {if(resizeDrag.current)setHeight(resizeDrag.current.height);resizeDrag.current=null;}}
        onKeyDown={e => {if(!['ArrowUp','ArrowDown','Home','End'].includes(e.key))return;e.preventDefault();setMinimized(false);setExpanded(false);setHeight(e.key==='Home'?240:e.key==='End'?maxHeight:Math.max(240,Math.min(maxHeight,viewHeight+(e.key==='ArrowUp'?40:-40))));}}><span/> <small>Drag to resize</small> <span/></div>
      <header>
        <strong>Free timeline</strong>
        <button className="free-size-button" aria-label={minimized ? "Restore minimized free timeline" : "Minimize free timeline"} title={minimized ? "Show the timeline tracks again" : "Hide tracks to give the preview more room"} onClick={() => setMinimized(!minimized)}>{minimized ? "Restore tracks" : "Minimize"}</button>
        <button
          aria-label={
            expanded ? "Restore free timeline" : "Maximize free timeline"
          }
          className="free-size-button"
          title={expanded ? "Return to your chosen timeline height" : "Show the largest timeline that fits this window"}
          onClick={() => {setMinimized(false);setExpanded(!expanded);}}
        >
          {expanded ? "Restore" : "Maximize"}
        </button>
        <button
          className="free-size-button"
          onClick={onViewSources}
          title="View original source scenes. Your free cuts and export remain active."
          disabled={disabled || pending}
        >
          Scene assembly
        </button>
        <button
          aria-label="Box select free clips"
          aria-pressed={boxMode}
          onClick={() => {
            setBoxMode(!boxMode);
            setRangeMode(false);
          }}
        >
          Box select
        </button>
        <button
          aria-label="Highlight free timeline range"
          aria-pressed={rangeMode}
          onClick={() => {
            setRangeMode(!rangeMode);
            setBoxMode(false);
          }}
        >
          Highlight range
        </button>
        <button
          disabled={!range || !selected.length || disabled || pending}
          onClick={() => {
            try {
              const result = cutFreeRange(
                project,
                selected,
                range!.a,
                range!.b,
              );
              void save(
                result.patch,
                "isolate highlighted timeline range",
              ).then((ok) => {
                if (ok) setSelected(result.selected);
              });
              setRange(null);
            } catch (e: any) {
              setError(e.message);
            }
          }}
        >
          Split highlighted range
        </button>
        <button aria-pressed={snap} onClick={() => setSnap(!snap)}>
          Snap
        </button>
        <button disabled={disabled || pending || !canUndo} onClick={onUndo}>
          Undo
        </button>
        <button disabled={disabled || pending || !canRedo} onClick={onRedo}>
          Redo
        </button>
        <button
          disabled={disabled || pending}
          onClick={() => void split()}
        >
          Split at playhead
        </button>
        <button
          disabled={!selected.length || disabled || pending}
          onClick={remove}
        >
          Remove clips
        </button>
        <button onClick={() => setPreview(!preview)}>
          {preview ? "Close free preview" : "Open free preview"}
        </button>
        <button
          onClick={() => {
            setPreview(true);
            setPlaying(!playing);
          }}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <button
          disabled={disabled || pending}
          onClick={() => void renderMissing()}
        >
          Render changed sources
        </button>
        <button disabled={disabled || pending} onClick={onExport}>
          Render full video
        </button>
        <label>
          Zoom
          <input
            aria-label="Free timeline zoom"
            type="range"
            min={20}
            max={180}
            value={scale}
            onChange={(e) => setScale(+e.target.value)}
          />
        </label>
      </header>
      <div className="free-content" hidden={minimized}>
      <p className="hint">
        Drag clips into empty space, left/right for time or up/down for track.
        Box-select pictures, text and audio to move them together. Split makes
        editable source excerpts. Double-click a clip to edit its source. Gaps
        export as black with silence; overlapping clips retain their own audio.
      </p>
      <div className="free-timeline-add">
        <select
          aria-label="Scene to place on free timeline"
          id="free-scene-choice"
        >
          {project.scenes
            .filter((s) => s.shots.length)
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
        </select>
        <button
          disabled={
            disabled || pending || !project.scenes.some((s) => s.shots.length)
          }
          onClick={() => {
            const id = (
                document.getElementById(
                  "free-scene-choice",
                ) as HTMLSelectElement
              ).value,
              scene = project.scenes.find((s) => s.id === id);
            if (scene) {
              const duration = sequenceClips([scene])[0].duration;
              void save(
                {
                  free_timeline: {
                    enabled: true,
                    clips: [
                      ...project.finishing_json!.free_timeline!.clips,
                      {
                        id: crypto.randomUUID(),
                        scene_id: id,
                        start_ms: Math.round(time),
                        source_in_ms: 0,
                        duration_ms: Math.round(duration),
                        track: 5,
                      },
                    ],
                  },
                },
                "place source scene at playhead",
              );
            }
          }}
        >
          Add scene at playhead
        </button>
        <button
          onClick={() =>
            window.dispatchEvent(
              new CustomEvent(ADD_TEXT, { detail: "text_box" }),
            )
          }
        >
          Add Text box at playhead
        </button>
        <label>
          Playhead (s)
          <input
            aria-label="Free timeline playhead seconds"
            type="number"
            min={0}
            step={0.1}
            value={(time / 1000).toFixed(2)}
            onChange={(e) => {setPlaying(false);setTime(Math.max(0, +e.target.value * 1000));}}
          />
        </label>
        <span>{selected.length} selected</span>
      </div>
      {error && <p role="alert">{error}</p>}
      {rendering && (
        <p role="status">
          {rendering}
          <button
            onClick={() => {
              cancel.current = true;
              if (job.current) void api.cancelJob(job.current);
            }}
          >
            Stop render
          </button>
        </p>
      )}
      <div className="free-scroll">
        <div className="free-labels">
          <div>Time</div>
          {Array.from({ length: lanes }, (_, i) => (
            <div key={i}>
              {i < 6
                ? "V" + (i + 1) + " · Picture / text"
                : "A" + (i - 3) + " · Audio"}
            </div>
          ))}
        </div>
        <div className="free-scroll-body">
          <div
            className="free-ruler"
            style={{ width }}
            onPointerDown={(e) => {
              const r = e.currentTarget.getBoundingClientRect();
              setPlaying(false);
              setTime(Math.max(0, ((e.clientX - r.left) / scale) * 1000));
            }}
          >
            {Array.from({ length: Math.ceil(width / scale / 2) }, (_, i) => (
              <span key={i} style={{ left: i * 2 * scale }}>
                {i * 2}s
              </span>
            ))}
          </div>
          <div
            ref={canvas}
            className="free-canvas"
            style={{ width, height: rowH * lanes }}
            onPointerDownCapture={(e) => {
              if (disabled || pending || e.button !== 0) return;
              const hit = (e.target as HTMLElement).closest<HTMLElement>(
                  "[data-free-key]",
                ),
                r = e.currentTarget.getBoundingClientRect();
              if (boxMode || rangeMode || !hit) {
                e.preventDefault();
                e.stopPropagation();
                gesture.current = {
                  kind: "box",
                  x: e.clientX - r.left,
                  y: e.clientY - r.top,
                  range: rangeMode,
                  previous: selected,
                };
                setBox({
                  x: e.clientX - r.left,
                  y: e.clientY - r.top,
                  width: 0,
                  height: 0,
                });
                e.currentTarget.setPointerCapture(e.pointerId);
              }
            }}
            onPointerMove={(e) => {
              const g = gesture.current;
              if (!g) return;
              const r = e.currentTarget.getBoundingClientRect();
              if (g.kind === "box") {
                const x = e.clientX - r.left,
                  y = e.clientY - r.top,
                  b = {
                    x: Math.min(x, g.x),
                    y: Math.min(y, g.y),
                    width: Math.abs(x - g.x),
                    height: Math.abs(y - g.y),
                  };
                setBox(b);
                if (g.range)
                  setRange({
                    a: Math.max(
                      0,
                      Math.round((Math.min(g.x, x) / scale) * 1000),
                    ),
                    b: Math.max(
                      0,
                      Math.round((Math.max(g.x, x) / scale) * 1000),
                    ),
                  });
                if (b.width > 4 || b.height > 4)
                  setSelected(
                    items
                      .filter(
                        (c) =>
                          b.x < ((c.start + c.duration) / 1000) * scale &&
                          b.x + b.width > (c.start / 1000) * scale &&
                          b.y < c.row * rowH + rowH - 3 &&
                          b.y + b.height > c.row * rowH + 3,
                      )
                      .map((c) => c.key),
                  );
              } else {
                if (Math.abs(e.clientX - g.x) < 3 && Math.abs(e.clientY - g.y) < 3) return;
                let delta = Math.round(
                  Math.round(
                    (((e.clientX - g.x - (r.left - g.canvasLeft)) / scale) *
                      1000) /
                      frame,
                  ) * frame,
                );
                if (snap) {
                  const lead = g.item.start + delta,
                    targets = [
                      0,
                      time,
                      ...freeItems(project)
                        .filter((c) => !g.keys.includes(c.key))
                        .flatMap((c) => [c.start, c.start + c.duration]),
                    ];
                  const near = targets.find(
                    (t) => (Math.abs(t - lead) / 1000) * scale < 8,
                  );
                  if (near !== undefined)
                    delta = Math.round(near - g.item.start);
                }
                const patch = moveFree(
                  project,
                  g.keys,
                  delta,
                  Math.round((e.clientY - g.y - (r.top - g.canvasTop)) / rowH),
                );
                last.current = patch;
                setMoving(patch);
              }
            }}
            onPointerUp={(e) => {
              const g = gesture.current;
              if (!g) return;
              gesture.current = null;
              if (e.currentTarget.hasPointerCapture(e.pointerId))
                e.currentTarget.releasePointerCapture(e.pointerId);
              if (g.kind === "box") {
                setBox(null);
                setBoxMode(false);
                setRangeMode(false);
              } else if (last.current)
                void save(last.current, "move free timeline selection");
            }}
            onPointerCancel={() => {
              gesture.current = null;
              setBox(null);
              setMoving(null);
            }}
          >
            {Array.from({ length: lanes }, (_, i) => (
              <div
                key={i}
                className="free-lane"
                style={{ top: i * rowH, height: rowH }}
                data-free-row={i}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => void drop(e, i)}
              />
            ))}
            {items.map((c) => (
              <button
                key={c.key}
                data-free-key={c.key}
                className={`free-clip free-${c.kind} ${selected.includes(c.key) ? "selected" : ""}`}
                style={{
                  left: (c.start / 1000) * scale,
                  top: c.row * rowH + 3,
                  width: Math.max(14, (c.duration / 1000) * scale - 2),
                  height: rowH - 6,
                  backgroundImage: thumbnail(c)
                    ? `linear-gradient(#252234aa,#252234dd),url("${thumbnail(c)}")`
                    : undefined,
                  backgroundSize: "cover",
                }}
                title={`${c.label} · ${(c.start / 1000).toFixed(2)} s · drag anywhere or double-click to edit original source`}
                onDoubleClick={() => choose(c)}
                onPointerDown={(e) => {
                  if (disabled || pending || e.button !== 0) return;
                  e.preventDefault();
                  e.stopPropagation();
                  const keys = selected.includes(c.key) ? selected : [c.key];
                  setSelected(keys);
                  gesture.current = {
                    kind: "move",
                    x: e.clientX,
                    y: e.clientY,
                    canvasLeft: canvas.current!.getBoundingClientRect().left,
                    canvasTop: canvas.current!.getBoundingClientRect().top,
                    item: c,
                    keys,
                  };
                  canvas.current!.setPointerCapture(e.pointerId);
                }}
              >
                {c.kind === "audio" &&
                  (() => {
                    const a = project.finishing_json?.audio_clips?.find(
                      (a) => a.id === c.id,
                    );
                    return a ? (
                      <AssetWave
                        assetId={a.asset_id}
                        fromMs={a.source_in_ms}
                        toMs={a.source_out_ms}
                      />
                    ) : null;
                  })()}
                <b>{c.label}</b>
                <small>
                  {c.kind === "scene"
                    ? "Source excerpt · picture, captions & sound"
                    : c.kind}{" "}
                  · {(c.duration / 1000).toFixed(1)}s
                </small>
              </button>
            ))}
            {range && (
              <div
                className="free-range"
                style={{
                  left: (range.a / 1000) * scale,
                  width: ((range.b - range.a) / 1000) * scale,
                }}
              />
            )}
            <div
              className="free-playhead"
              style={{ left: (time / 1000) * scale }}
            />
            {box && (
              <div
                className="scene-selection-box"
                style={{
                  left: box.x,
                  top: box.y,
                  width: box.width,
                  height: box.height,
                }}
              />
            )}
          </div>
        </div>
      </div>
      </div>
      {preview &&
        host &&
        createPortal(
          <FreePreview
            project={current}
            time={time}
            playing={playing}
            onClose={() => {
              setPreview(false);
              setPlaying(false);
            }}
          />,
          host,
        )}
    </section>
  );
}
function FreeMedia({
  src,
  local,
  playing,
  audio = false,
  volume = 1,
  label,
}: {
  src: string;
  local: number;
  playing: boolean;
  audio?: boolean;
  volume?: number;
  label: string;
}) {
  const ref = useRef<HTMLMediaElement | null>(null);
  const sync = () => {
    const el = ref.current;
    if (!el) return;
    el.volume=Math.max(0,Math.min(1,volume));
    const t = local / 1000;
    if (el.readyState >= 1 && Math.abs(el.currentTime - t) > 0.15)
      el.currentTime = t;
    if (playing) void el.play().catch(() => {});
    else el.pause();
  };
  useEffect(sync, [local, playing, src,volume]);
  useEffect(()=>{const el=ref.current;return()=>el?.pause();},[]);
  return audio ? (
    <audio
      ref={(el) => {
        ref.current = el;
      }}
      src={src}
      onLoadedMetadata={sync}
    />
  ) : (
    <video
      ref={(el) => {
        ref.current = el;
      }}
      src={src}
      aria-label={label}
      playsInline
      onLoadedMetadata={sync}
    />
  );
}
function FreePreview({
  project,
  time,
  playing,
  onClose,
}: {
  project: Project;
  time: number;
  playing: boolean;
  onClose: () => void;
}) {
  const clips = (project.finishing_json?.free_timeline?.clips || [])
    .filter((c) => time >= c.start_ms && time < c.start_ms + c.duration_ms)
    .sort((a, b) => b.track - a.track);
  return (
    <div
      className="program-monitor free-monitor"
      aria-label="Free timeline preview"
    >
      <header>
        <strong>Free timeline preview</strong>
        <span>
          {(time / 1000).toFixed(2)}s · render changed sources for exact effects
        </span>
        <button onClick={onClose}>Close</button>
      </header>
      <div
        className="free-preview-frame"
        style={{ aspectRatio: project.width / project.height }}
      >
        {clips.map((c) => {
          const s = project.scenes.find((s) => s.id === c.scene_id);
          return s?.rendered_asset_id && !s.is_stale ? (
            <div
              className="free-preview-item"
              key={c.id}
              style={{ zIndex: 6 - c.track }}
            >
              <FreeMedia
                src={api.assetStreamUrl(s.rendered_asset_id)}
                local={time - c.start_ms + c.source_in_ms}
                playing={playing}
                label={s.title}
              />
            </div>
          ) : (
            <div
              key={c.id}
              className="free-source-missing"
              style={{ zIndex: 6 - c.track }}
            >
              {s?.title} — render changed sources to preview
            </div>
          );
        })}
        {(project.finishing_json?.layer_clips || []).map((c) => (
          <div
            className="free-preview-item"
            key={c.id}
            style={{ zIndex: 6 - c.track }}
          >
            <LayerPreview
              project={{
                ...project,
                finishing_json: { ...project.finishing_json, layer_clips: [c] },
              }}
              time={time}
              playing={playing}
            />
          </div>
        ))}
        {(project.finishing_json?.audio_clips || [])
          .filter(
            (c) =>
              !c.mute &&
              time >= c.start_ms &&
              time < c.start_ms + c.source_out_ms - c.source_in_ms,
          )
          .map((c) => (
            <FreeMedia
              key={c.id}
              src={api.assetStreamUrl(c.asset_id)}
              local={time - c.start_ms + c.source_in_ms}
              playing={playing}
              audio
              volume={c.volume/100}
              label={c.name}
            />
          ))}
      </div>
      <p className="hint">
        Source scene styling is rendered. Timeline audio fades, bleep and gain
        are checked in Render full video.
      </p>
    </div>
  );
}
