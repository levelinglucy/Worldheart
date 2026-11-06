#!/usr/bin/env python3
# WORLDHEART v0.2.1-rc1 — PRIMORDIAL FIELD (probe isolation candidate)
# Developer summary: prevents counterfactual probes from writing world files.
# Prior baseline: "Worldheart simulator" (v0.2). More: DEV_NOTES.md.
# Next: validate original-vs-candidate regression, then review promotion.
# A self-contained emergent computational petri dish for Python / Pythonista.
#
# Design:
# - No Agent, Creature, Language, Goal, Emotion, or Consciousness classes.
# - Evolving structures are byte strings executed by a tiny bounded VM.
# - Persistence emerges from continued existence / copying, not a fitness score.
# - Mutable graph substrate; structures can alter local state and topology.
# - Deterministic seeded runs.
# - External observer metrics, anomaly fossils, checkpoints, and replayable saves.
#
# Standard library only.

import os
import sys
import json
import math
import time
import random
import hashlib
import pickle
import zlib
import statistics
from dataclasses import dataclass, field, asdict
from collections import Counter, defaultdict, deque

# ─────────────────────────────────────────────────────────────────────────────
# 00. CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

VERSION = "0.2.1-rc1"
DEFAULT_SEED = 18481921

NODE_COUNT = 96
INITIAL_STRUCTURES = 72
INITIAL_CODE_MIN = 6
INITIAL_CODE_MAX = 24

MAX_STRUCTURES = 1800
MAX_CODE_LEN = 96
MAX_EDGES_PER_NODE = 8
MAX_NODE_VALUE = 255
MAX_REGISTER = 65535

TICKS_PER_FRAME = 120
OPS_PER_STRUCTURE = 12
BASE_ENERGY = 22
MAX_ENERGY = 96

MUTATE_BYTE_P = 0.018
INSERT_BYTE_P = 0.006
DELETE_BYTE_P = 0.005
COPY_MUTATION_MULTIPLIER = 1.15

CHECKPOINT_EVERY = 25000
METRICS_EVERY = 500
ANOMALY_COOLDOWN = 2500
FOSSIL_LIMIT = 80

SAVE_DIR = "WORLDHEART_V02_DATA"
SAVE_FILE = "worldheart_v02_latest.wh"
EVENT_FILE = "worldheart_v02_events.jsonl"

# The VM opcodes are intentionally numeric. Human-readable names exist only
# in this external observer/debug layer.
OP_COUNT = 32

# ─────────────────────────────────────────────────────────────────────────────
# 01. UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def stable_hash(data):
    if not isinstance(data, (bytes, bytearray)):
        data = repr(data).encode("utf-8", "replace")
    return hashlib.blake2b(data, digest_size=8).hexdigest()

def entropy_bytes(values):
    if not values:
        return 0.0
    c = Counter(values)
    n = len(values)
    return -sum((k/n) * math.log2(k/n) for k in c.values())

def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0

def safe_mkdir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

def clear_screen():
    # Pythonista's console does not interpret normal ANSI clear sequences.
    # Form-feed is harmless in ordinary terminals and avoids visible "[2J[H".
    print("\f", end="")

# ─────────────────────────────────────────────────────────────────────────────
# 02. SUBSTRATE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Node:
    value: int = 0
    charge: int = 0
    mark: int = 0
    edges: set = field(default_factory=set)

@dataclass
class Structure:
    sid: int
    code: bytearray
    node: int
    energy: int
    parent: int = 0
    lineage: int = 0
    born: int = 0
    age: int = 0
    ip: int = 0
    regs: list = field(default_factory=lambda: [0, 0, 0, 0])
    stack: list = field(default_factory=list)
    alive: bool = True
    copies: int = 0
    interactions: int = 0
    writes: int = 0
    topology_edits: int = 0
    signature: str = ""

    def refresh_signature(self):
        self.signature = stable_hash(bytes(self.code))

# ─────────────────────────────────────────────────────────────────────────────
# 03. WORLD
# ─────────────────────────────────────────────────────────────────────────────

class World:
    def __init__(self, seed=DEFAULT_SEED):
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.tick = 0
        self.next_sid = 1
        self.nodes = [Node(self.rng.randrange(256),
                           self.rng.randrange(-8, 9),
                           self.rng.randrange(256))
                      for _ in range(NODE_COUNT)]
        self.structures = {}
        self.dead_lineages = Counter()
        self.lineage_births = Counter()
        self.lineage_deaths = Counter()
        self.events = deque(maxlen=250)
        self.fossils = []
        self.metrics_history = deque(maxlen=200)
        self.last_metrics_tick = -METRICS_EVERY
        self.last_anomaly_tick = -ANOMALY_COOLDOWN
        self.total_births = 0
        self.total_deaths = 0
        self.total_mutations = 0
        self.total_topology_edits = 0
        self.total_writes = 0
        self.total_ops = 0
        self.provenance = deque(maxlen=5000)
        self.milestones = set()
        self._disk_writes_enabled = True  # Legacy worlds default to True via _can_write_disk().
        self.genesis()

    def genesis(self):
        # Ring + sparse random chords. No geometry is exposed to structures.
        n = len(self.nodes)
        for i in range(n):
            self.link(i, (i + 1) % n)
            if self.rng.random() < 0.35:
                self.link(i, self.rng.randrange(n))

        for _ in range(INITIAL_STRUCTURES):
            ln = self.rng.randint(INITIAL_CODE_MIN, INITIAL_CODE_MAX)
            code = bytearray(self.rng.randrange(256) for _ in range(ln))
            node = self.rng.randrange(n)
            self.spawn(code, node, parent=0, lineage=None,
                       energy=self.rng.randint(12, BASE_ENERGY + 12))
        self.event("GENESIS", {"seed": self.seed, "structures": len(self.structures)})

    def _can_write_disk(self):
        """Read-through for old pickled worlds without a disk-writes flag."""
        return getattr(self, "_disk_writes_enabled", True)

    def event(self, kind, data):
        e = {"tick": self.tick, "kind": kind, "data": data}
        self.events.append(e)
        if not self._can_write_disk():
            return  # Counterfactual forks keep events in memory only.
        try:
            safe_mkdir(SAVE_DIR)
            with open(os.path.join(SAVE_DIR, EVENT_FILE), "a", encoding="utf-8") as f:
                f.write(json.dumps(e, separators=(",", ":")) + "\n")
        except Exception:
            pass

    def provenance_event(self, kind, **data):
        rec = {"tick": self.tick, "kind": kind, **data}
        self.provenance.append(rec)
        return rec

    def milestone(self, key, data):
        if key in self.milestones:
            return
        self.milestones.add(key)
        self.event("MILESTONE", {"key": key, **data})
        self.preserve_fossil(["first " + key.replace("_", " ")], self.metrics())

    def link(self, a, b):
        if a == b:
            return False
        if not (0 <= a < len(self.nodes) and 0 <= b < len(self.nodes)):
            return False
        if len(self.nodes[a].edges) >= MAX_EDGES_PER_NODE:
            return False
        if len(self.nodes[b].edges) >= MAX_EDGES_PER_NODE:
            return False
        self.nodes[a].edges.add(b)
        self.nodes[b].edges.add(a)
        return True

    def unlink(self, a, b):
        if b in self.nodes[a].edges:
            self.nodes[a].edges.discard(b)
            self.nodes[b].edges.discard(a)
            return True
        return False

    def spawn(self, code, node, parent=0, lineage=None, energy=BASE_ENERGY):
        if len(self.structures) >= MAX_STRUCTURES or not code:
            return None
        code = bytearray(code[:MAX_CODE_LEN])
        sid = self.next_sid
        self.next_sid += 1
        if lineage is None:
            lineage = sid
        s = Structure(sid=sid, code=code, node=node % len(self.nodes),
                      energy=clamp(int(energy), 1, MAX_ENERGY),
                      parent=parent, lineage=lineage, born=self.tick)
        s.refresh_signature()
        self.structures[sid] = s
        self.lineage_births[lineage] += 1
        self.total_births += 1
        if parent:
            p = self.structures.get(parent)
            self.provenance_event(
                "BIRTH", child=sid, parent=parent, lineage=lineage,
                parent_signature=(p.signature if p else None),
                child_signature=s.signature, node=s.node
            )
        return s

    def kill(self, s):
        if not s.alive:
            return
        s.alive = False
        self.structures.pop(s.sid, None)
        self.lineage_deaths[s.lineage] += 1
        self.total_deaths += 1

    def mutate(self, code, multiplier=1.0):
        out = bytearray(code)
        changed = False
        for i in range(len(out)):
            if self.rng.random() < MUTATE_BYTE_P * multiplier:
                # Local and nonlocal byte mutations both possible.
                if self.rng.random() < 0.7:
                    out[i] = (out[i] + self.rng.choice((-17,-5,-1,1,5,17))) & 255
                else:
                    out[i] = self.rng.randrange(256)
                changed = True
        if len(out) < MAX_CODE_LEN and self.rng.random() < INSERT_BYTE_P * multiplier:
            out.insert(self.rng.randrange(len(out) + 1), self.rng.randrange(256))
            changed = True
        if len(out) > 1 and self.rng.random() < DELETE_BYTE_P * multiplier:
            del out[self.rng.randrange(len(out))]
            changed = True
        if changed:
            self.total_mutations += 1
        return out

    def local_ids(self, node):
        return [sid for sid, s in self.structures.items() if s.node == node]

    def neighbor_node(self, node, selector):
        edges = sorted(self.nodes[node].edges)
        if not edges:
            return node
        return edges[selector % len(edges)]

    # ─────────────────────────────────────────────────────────────────────────
    # 04. EVOLVABLE VIRTUAL MACHINE
    # ─────────────────────────────────────────────────────────────────────────
    #
    # Bytes map to 32 primitive transformations by byte % OP_COUNT.
    # The evolving substrate sees bytes and consequences, never these labels.
    #
    def execute_one(self, s):
        if not s.alive or not s.code:
            return
        s.ip %= len(s.code)
        raw = s.code[s.ip]
        op = raw % OP_COUNT
        arg = s.code[(s.ip + 1) % len(s.code)] if len(s.code) > 1 else raw
        r = arg & 3
        n = self.nodes[s.node]
        s.ip = (s.ip + 1) % len(s.code)
        self.total_ops += 1

        # 0–3: internal transformations
        if op == 0:
            s.regs[r] = (s.regs[r] + 1) & MAX_REGISTER
        elif op == 1:
            s.regs[r] = (s.regs[r] - 1) & MAX_REGISTER
        elif op == 2:
            s.regs[r] ^= arg
        elif op == 3:
            s.regs[r] = ((s.regs[r] << 1) | (s.regs[r] >> 15)) & MAX_REGISTER

        # 4–9: substrate sensing / writing
        elif op == 4:
            s.regs[r] = n.value
        elif op == 5:
            s.regs[r] = n.mark
        elif op == 6:
            s.regs[r] = n.charge & MAX_REGISTER
        elif op == 7:
            n.value = (n.value + (s.regs[r] & 15) - 7) & 255
            s.writes += 1; self.total_writes += 1
        elif op == 8:
            n.mark = (n.mark ^ (s.regs[r] & 255)) & 255
            s.writes += 1; self.total_writes += 1
        elif op == 9:
            delta = ((s.regs[r] & 7) - 3)
            n.charge = clamp(n.charge + delta, -64, 64)
            s.writes += 1; self.total_writes += 1

        # 10–13: movement through mutable topology
        elif op == 10:
            s.node = self.neighbor_node(s.node, s.regs[r] + arg)
        elif op == 11:
            target = self.neighbor_node(s.node, arg)
            s.regs[r] = self.nodes[target].value
        elif op == 12:
            target = self.neighbor_node(s.node, arg)
            if self.link(s.node, (target + (s.regs[r] & 15)) % len(self.nodes)):
                s.topology_edits += 1; self.total_topology_edits += 1
        elif op == 13:
            edges = sorted(n.edges)
            if edges:
                target = edges[arg % len(edges)]
                if len(edges) > 1 and self.unlink(s.node, target):
                    s.topology_edits += 1; self.total_topology_edits += 1

        # 14–17: control flow / local state
        elif op == 14:
            if s.regs[r] & 1:
                s.ip = (s.ip + (arg % max(1, len(s.code)))) % len(s.code)
        elif op == 15:
            if n.value < (s.regs[r] & 255):
                s.ip = (s.ip - (arg % max(1, len(s.code)))) % len(s.code)
        elif op == 16:
            if len(s.stack) < 12:
                s.stack.append(s.regs[r])
        elif op == 17:
            if s.stack:
                s.regs[r] = s.stack.pop()

        # 18–21: code plasticity
        elif op == 18:
            if s.code:
                idx = s.regs[r] % len(s.code)
                s.code[idx] ^= arg
                s.refresh_signature()
        elif op == 19:
            if len(s.code) < MAX_CODE_LEN:
                idx = s.regs[r] % (len(s.code) + 1)
                s.code.insert(idx, arg)
                s.refresh_signature()
        elif op == 20:
            if len(s.code) > 1:
                idx = s.regs[r] % len(s.code)
                del s.code[idx]
                s.ip %= len(s.code)
                s.refresh_signature()
        elif op == 21:
            if len(s.code) > 2:
                a = s.regs[r] % len(s.code)
                b = arg % len(s.code)
                s.code[a], s.code[b] = s.code[b], s.code[a]
                s.refresh_signature()

        # 22–25: replication / recombination
        elif op == 22:
            cost = 7 + len(s.code) // 8
            if s.energy > cost and len(self.structures) < MAX_STRUCTURES:
                child_code = self.mutate(s.code, COPY_MUTATION_MULTIPLIER)
                child_node = self.neighbor_node(s.node, arg)
                child = self.spawn(child_code, child_node, s.sid, s.lineage,
                                   max(2, s.energy // 3))
                if child:
                    s.energy -= cost
                    s.copies += 1
                    self.provenance_event(
                        "COPY", parent=s.sid, child=child.sid, lineage=s.lineage,
                        parent_signature=s.signature,
                        child_signature=child.signature,
                        changed=(s.signature != child.signature)
                    )
                    self.milestone("replication", {
                        "parent": s.sid, "child": child.sid,
                        "changed": s.signature != child.signature
                    })
                    if s.signature != child.signature:
                        self.milestone("mutation_descendant", {
                            "parent": s.sid, "child": child.sid
                        })
        elif op == 23:
            locals_ = [self.structures[x] for x in self.local_ids(s.node)
                       if x != s.sid and x in self.structures]
            if locals_ and s.energy > 8:
                other = locals_[arg % len(locals_)]
                cut1 = (s.regs[r] % len(s.code)) if s.code else 0
                cut2 = arg % len(other.code)
                mixed = (s.code[:cut1] + other.code[cut2:])[:MAX_CODE_LEN]
                if mixed:
                    child = self.spawn(self.mutate(mixed), s.node, s.sid,
                                       s.lineage, max(2, s.energy // 4))
                    if child:
                        s.energy -= 8
                        s.interactions += 1
                        other.interactions += 1
                        self.provenance_event(
                            "RECOMBINATION", parent_a=s.sid, parent_b=other.sid,
                            child=child.sid, lineage=child.lineage,
                            child_signature=child.signature
                        )
                        self.milestone("recombination", {
                            "parent_a": s.sid, "parent_b": other.sid,
                            "child": child.sid
                        })
        elif op == 24:
            locals_ = [self.structures[x] for x in self.local_ids(s.node)
                       if x != s.sid and x in self.structures]
            if locals_:
                other = locals_[arg % len(locals_)]
                idx = s.regs[r] % len(s.code)
                j = arg % len(other.code)
                s.code[idx] = other.code[j]
                s.refresh_signature()
                s.interactions += 1
        elif op == 25:
            # Deposit a code-derived environmental trace.
            n.mark ^= int(s.signature[:2], 16)
            n.mark &= 255
            s.writes += 1; self.total_writes += 1

        # 26–29: energy coupling to substrate / others
        elif op == 26:
            # Charge gradients can be harvested but are depleted by doing so.
            if n.charge > 0 and s.energy < MAX_ENERGY:
                gain = min(3, n.charge, MAX_ENERGY - s.energy)
                s.energy += gain
                n.charge -= gain
        elif op == 27:
            # Convert internal energy into local charge.
            if s.energy > 3:
                s.energy -= 2
                n.charge = clamp(n.charge + 2, -64, 64)
        elif op == 28:
            locals_ = [self.structures[x] for x in self.local_ids(s.node)
                       if x != s.sid and x in self.structures]
            if locals_ and s.energy > 2:
                other = locals_[arg % len(locals_)]
                s.energy -= 1
                other.energy = min(MAX_ENERGY, other.energy + 1)
                s.interactions += 1; other.interactions += 1
        elif op == 29:
            locals_ = [self.structures[x] for x in self.local_ids(s.node)
                       if x != s.sid and x in self.structures]
            if locals_:
                other = locals_[arg % len(locals_)]
                if other.energy > 1:
                    other.energy -= 1
                    s.energy = min(MAX_ENERGY, s.energy + 1)
                    s.interactions += 1; other.interactions += 1

        # 30–31: state-dependent code addressing / quiescence
        elif op == 30:
            if s.code:
                s.ip = (s.ip + n.value + n.mark + s.regs[r]) % len(s.code)
        elif op == 31:
            # A no-op can be advantageous because every other operation has
            # opportunity cost; no special semantic reward is attached.
            pass

        # External observer milestones. These do not feed back into the world.
        if s.writes > 0:
            self.milestone("environment_write", {"sid": s.sid, "lineage": s.lineage})
        if s.topology_edits > 0:
            self.milestone("topology_edit", {"sid": s.sid, "lineage": s.lineage})

    # ─────────────────────────────────────────────────────────────────────────
    # 05. PHYSICS / TRANSITIONS
    # ─────────────────────────────────────────────────────────────────────────

    def environmental_step(self):
        # Dynamic substrate: charge diffuses; values drift weakly.
        # This is "physics", not an objective.
        if not self.nodes:
            return
        for _ in range(max(1, len(self.nodes) // 8)):
            a = self.rng.randrange(len(self.nodes))
            if not self.nodes[a].edges:
                continue
            b = self.rng.choice(tuple(self.nodes[a].edges))
            na, nb = self.nodes[a], self.nodes[b]
            if na.charge > nb.charge + 1:
                na.charge -= 1; nb.charge += 1
            elif nb.charge > na.charge + 1:
                nb.charge -= 1; na.charge += 1

        # v0.2 primordial field: weak, distributed, fluctuating resource flux.
        # It has no semantic label inside the substrate.
        pulses = max(2, len(self.nodes) // 24)
        for j in range(pulses):
            flux_node = (self.tick * (17 + 2*j) + self.seed + 31*j) % len(self.nodes)
            pulse = 1 + ((self.tick + j + self.seed) % 3)
            self.nodes[flux_node].charge = min(64, self.nodes[flux_node].charge + pulse)

        if self.rng.random() < 0.08:
            n = self.nodes[self.rng.randrange(len(self.nodes))]
            n.value = (n.value + self.rng.choice((-1, 1))) & 255

    def transition(self):
        self.tick += 1
        self.environmental_step()

        ids = list(self.structures.keys())
        self.rng.shuffle(ids)

        for sid in ids:
            s = self.structures.get(sid)
            if not s:
                continue

            s.age += 1

            # v0.2: existence is passive. Computation, not mere persistence,
            # consumes the replenishable resource. A quiescent byte structure
            # can therefore remain as "material" without being rewarded.
            n = self.nodes[s.node]

            # Local charge can wake/energize a structure.
            if n.charge > 0 and s.energy < MAX_ENERGY:
                gain = min(2, n.charge, MAX_ENERGY - s.energy)
                s.energy += gain
                n.charge -= gain

            # Zero-energy structures persist but do not execute.
            if s.energy <= 0:
                continue

            budget = min(OPS_PER_STRUCTURE, max(1, s.energy // 4))
            for op_index in range(budget):
                if s.sid not in self.structures or s.energy <= 0:
                    break
                self.execute_one(s)
                # Active computation has opportunity/resource cost.
                if (op_index + 1) % 3 == 0:
                    s.energy = max(0, s.energy - 1)

        if self.tick - self.last_metrics_tick >= METRICS_EVERY:
            self.last_metrics_tick = self.tick
            m = self.metrics()
            self.metrics_history.append(m)
            self.detect_anomalies(m)

        if self._can_write_disk() and CHECKPOINT_EVERY and self.tick % CHECKPOINT_EVERY == 0:
            self.save()

    # ─────────────────────────────────────────────────────────────────────────
    # 06. OBSERVER / MEASUREMENT
    # ─────────────────────────────────────────────────────────────────────────

    def metrics(self):
        ss = list(self.structures.values())
        codes = [b for s in ss for b in s.code]
        signatures = Counter(s.signature for s in ss)
        lineages = Counter(s.lineage for s in ss)
        ages = [s.age for s in ss]
        energies = [s.energy for s in ss]
        degrees = [len(n.edges) for n in self.nodes]

        # Compression proxy: repeated signatures + byte entropy + structural
        # diversity. It does not assign semantic intelligence.
        byte_h = entropy_bytes(codes) / 8.0 if codes else 0.0
        diversity = len(signatures) / max(1, len(ss))
        persistence = max(ages) if ages else 0
        lineage_depth_proxy = max((self.lineage_births[k] for k in lineages), default=0)

        return {
            "tick": self.tick,
            "active": len(ss),
            "distinct_patterns": len(signatures),
            "lineages": len(lineages),
            "mean_age": mean(ages),
            "max_age": persistence,
            "mean_energy": mean(energies),
            "byte_entropy": byte_h,
            "diversity": diversity,
            "mean_degree": mean(degrees),
            "births": self.total_births,
            "deaths": self.total_deaths,
            "mutations": self.total_mutations,
            "writes": self.total_writes,
            "topology_edits": self.total_topology_edits,
            "ops": self.total_ops,
            "lineage_depth_proxy": lineage_depth_proxy,
        }

    def detect_anomalies(self, m):
        if self.tick - self.last_anomaly_tick < ANOMALY_COOLDOWN:
            return
        reasons = []
        hist = list(self.metrics_history)
        if len(hist) >= 8:
            prev = hist[-8:-1]
            old_active = mean([x["active"] for x in prev])
            old_age = mean([x["max_age"] for x in prev])
            old_div = mean([x["diversity"] for x in prev])
            if old_active > 4 and m["active"] > old_active * 1.8:
                reasons.append("population discontinuity")
            if old_age > 20 and m["max_age"] > old_age * 2.2:
                reasons.append("unusual persistence")
            if m["diversity"] > old_div + 0.22:
                reasons.append("diversity discontinuity")

        # Detect a lineage becoming disproportionately represented without
        # assigning that success a purpose.
        counts = Counter(s.lineage for s in self.structures.values())
        if counts and m["active"] >= 30:
            lin, count = counts.most_common(1)[0]
            frac = count / m["active"]
            if frac > 0.58:
                reasons.append("lineage concentration %.2f" % frac)

        # Detect persistent external writing / topology construction.
        if self.structures:
            standout = max(self.structures.values(),
                           key=lambda s: s.writes + 3*s.topology_edits + s.copies)
            activity = standout.writes + 3*standout.topology_edits + standout.copies
            if standout.age > 1000 and activity > 80:
                reasons.append("persistent environment modification")

        if reasons:
            self.last_anomaly_tick = self.tick
            self.preserve_fossil(reasons, m)

    def preserve_fossil(self, reasons, metrics):
        # Store a compact, immutable observational fossil. Full world snapshots
        # remain available through checkpoints.
        top = sorted(self.structures.values(),
                     key=lambda s: (s.age, s.copies, s.writes), reverse=True)[:12]
        fossil = {
            "tick": self.tick,
            "reasons": list(reasons),
            "metrics": dict(metrics),
            "structures": [{
                "sid": s.sid,
                "lineage": s.lineage,
                "age": s.age,
                "signature": s.signature,
                "code_hex": bytes(s.code).hex(),
                "node": s.node,
                "copies": s.copies,
                "writes": s.writes,
                "topology_edits": s.topology_edits,
            } for s in top]
        }
        self.fossils.append(fossil)
        if len(self.fossils) > FOSSIL_LIMIT:
            self.fossils = self.fossils[-FOSSIL_LIMIT:]
        self.event("ANOMALY", {"reasons": reasons})
        if not self._can_write_disk():
            return  # Fossil remains inspectable on the private fork only.
        try:
            safe_mkdir(SAVE_DIR)
            fn = "fossil_%012d.json" % self.tick
            with open(os.path.join(SAVE_DIR, fn), "w", encoding="utf-8") as f:
                json.dump(fossil, f, indent=2)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # 07. CHECKPOINT / RECOVERY
    # ─────────────────────────────────────────────────────────────────────────

    def save(self, filename=None):
        if not self._can_write_disk():
            raise RuntimeError("Counterfactual fork: disk persistence is disabled")
        safe_mkdir(SAVE_DIR)
        filename = filename or os.path.join(SAVE_DIR, SAVE_FILE)
        state = pickle.dumps(self, protocol=pickle.HIGHEST_PROTOCOL)
        payload = zlib.compress(state, 6)
        envelope = {
            "version": VERSION,
            "seed": self.seed,
            "tick": self.tick,
            "hash": stable_hash(payload),
            "payload": payload.hex(),
        }
        temp = filename + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(envelope, f)
        os.replace(temp, filename)
        self.event("CHECKPOINT", {"file": filename})
        return filename

    def save_named(self, label=None):
        if not self._can_write_disk():
            raise RuntimeError("Counterfactual fork: disk persistence is disabled")
        safe_mkdir(SAVE_DIR)
        if not label:
            label = "checkpoint"
        clean = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(label))[:40]
        filename = os.path.join(
            SAVE_DIR, "%s_t%012d.wh" % (clean or "checkpoint", self.tick)
        )
        return self.save(filename)

    @staticmethod
    def load(filename=None):
        filename = filename or os.path.join(SAVE_DIR, SAVE_FILE)
        with open(filename, "r", encoding="utf-8") as f:
            envelope = json.load(f)
        payload = bytes.fromhex(envelope["payload"])
        if stable_hash(payload) != envelope["hash"]:
            raise ValueError("Checkpoint integrity failure")
        world = pickle.loads(zlib.decompress(payload))
        return world

    def fork(self, disk_writes_enabled=None):
        """Clone state/RNG; optionally forbid ALL fork-generated disk artifacts.

        None preserves the parent's setting (legacy public behaviour). Probes
        explicitly pass False; disabling writes does not change VM evolution.
        """
        copy = pickle.loads(pickle.dumps(self, protocol=pickle.HIGHEST_PROTOCOL))
        if disk_writes_enabled is not None:
            copy._disk_writes_enabled = bool(disk_writes_enabled)
        return copy

# ─────────────────────────────────────────────────────────────────────────────
# 08. COUNTERFACTUAL LAB
# ─────────────────────────────────────────────────────────────────────────────

def counterfactual_probe(world, steps=300):
    """Run non-destructive forks around the oldest currently persistent form."""
    if not world.structures:
        return None
    target = max(world.structures.values(), key=lambda s: s.age)
    control = world.fork(disk_writes_enabled=False)
    altered = world.fork(disk_writes_enabled=False)

    altered_target = altered.structures.get(target.sid)
    if altered_target:
        altered.kill(altered_target)

    before_c = control.metrics()
    before_a = altered.metrics()

    for _ in range(steps):
        control.transition()
        altered.transition()

    after_c = control.metrics()
    after_a = altered.metrics()

    return {
        "target_sid": target.sid,
        "target_signature": target.signature,
        "target_age": target.age,
        "steps": steps,
        "control": after_c,
        "removed": after_a,
        "delta_active": after_c["active"] - after_a["active"],
        "delta_lineages": after_c["lineages"] - after_a["lineages"],
        "delta_diversity": after_c["diversity"] - after_a["diversity"],
    }

# ─────────────────────────────────────────────────────────────────────────────
# 09. CUTE EXTERNAL OBSERVER
# ─────────────────────────────────────────────────────────────────────────────

SPARKS = " ·∙○◌●◉"

def tiny_map(world, width=42, height=10):
    # Observer-only projection of graph occupancy. It is not the world's space.
    occ = Counter(s.node for s in world.structures.values())
    lines = []
    for y in range(height):
        row = []
        for x in range(width):
            idx = (x + y * width) % len(world.nodes)
            amount = occ.get(idx, 0)
            if amount == 0:
                ch = "·" if world.nodes[idx].charge > 10 else " "
            elif amount == 1:
                ch = "∙"
            elif amount < 4:
                ch = "○"
            elif amount < 10:
                ch = "◌"
            elif amount < 25:
                ch = "●"
            else:
                ch = "◉"
            row.append(ch)
        lines.append("".join(row))
    return lines

def bar(v, maxv=1.0, width=12):
    v = clamp(v / maxv if maxv else 0, 0, 1)
    n = int(round(v * width))
    return "█" * n + "░" * (width - n)

def render(world, paused=False):
    m = world.metrics()
    clear_screen()
    print("╭──────────────── WORLDHEART 🧫 ────────────────╮")
    print("│ v%-12s  seed %-12s %s │" %
          (VERSION[:12], str(world.seed)[:12], "PAUSED" if paused else "RUNNING"))
    print("├───────────────────────────────────────────────┤")
    for line in tiny_map(world):
        print("│  %-43s│" % line[:43])
    print("├───────────────────────────────────────────────┤")
    print("│ transition      %-29s│" % f"{world.tick:,}")
    print("│ active forms    %-29s│" % f"{m['active']:,}")
    print("│ pattern forms   %-29s│" % f"{m['distinct_patterns']:,}")
    print("│ lineages        %-29s│" % f"{m['lineages']:,}")
    print("│ oldest          %-29s│" % f"{m['max_age']:,}")
    print("│ entropy         %-12s %-16.3f│" % (bar(m["byte_entropy"]), m["byte_entropy"]))
    print("│ diversity       %-12s %-16.3f│" % (bar(m["diversity"]), m["diversity"]))
    print("│ fossils         %-29s│" % len(world.fossils))
    print("├───────────────────────────────────────────────┤")
    recent = [e for e in world.events if e["kind"] == "ANOMALY"]
    if recent:
        r = recent[-1]
        msg = ", ".join(r["data"].get("reasons", []))[:39]
        print("│ 👁 %-42s│" % msg)
    else:
        print("│ 👁 observer has no anomaly to report          │")
    print("├───────────────────────────────────────────────┤")
    print("│ Enter: run   p:pause   i:inspect   c:probe    │")
    print("│ s:save       f:fossils q:save & quit          │")
    print("╰───────────────────────────────────────────────╯")

def inspect(world):
    clear_screen()
    print("WORLDHEART — OBSERVER MICROSCOPE\n")
    if not world.structures:
        print("No active structures.")
        input("\nEnter to return.")
        return
    top = sorted(world.structures.values(),
                 key=lambda s: (s.age, s.copies, s.writes, s.interactions),
                 reverse=True)[:15]
    print(" sid      lin      parent   age  en  len copies writes topo  signature")
    print("-" * 84)
    for s in top:
        print("%-8d %-8d %-8d %-5d %-3d %-3d %-6d %-6d %-5d %s" %
              (s.sid, s.lineage, s.parent, s.age, s.energy, len(s.code),
               s.copies, s.writes, s.topology_edits, s.signature))
    print("\nRecent provenance:")
    for e in list(world.provenance)[-8:]:
        print(" t=%s  %s  %s" % (e.get("tick"), e.get("kind"),
                                 {k:v for k,v in e.items() if k not in ("tick","kind")}))
    print("\nObserver note: these are measurements, not semantic labels.")
    input("\nEnter to return.")

def show_fossils(world):
    clear_screen()
    print("WORLDHEART — FOSSILS\n")
    if not world.fossils:
        print("No anomaly fossils preserved yet.")
    for f in world.fossils[-15:]:
        print("t=%-12s  %s" % (f["tick"], ", ".join(f["reasons"])))
    input("\nEnter to return.")

def show_probe(world):
    clear_screen()
    print("WORLDHEART — COUNTERFACTUAL LAB\n")
    print("Creating two private copies. The primary universe will not be touched.\n")
    result = counterfactual_probe(world, 300)
    if not result:
        print("No active structure to probe.")
    else:
        print("Target:       ", result["target_sid"], result["target_signature"])
        print("Observed age: ", result["target_age"])
        print("Fork horizon: ", result["steps"], "transitions")
        print("\nControl active: ", result["control"]["active"])
        print("Removed active: ", result["removed"]["active"])
        print("Δ active:       ", result["delta_active"])
        print("Δ lineages:     ", result["delta_lineages"])
        print("Δ diversity:    ", round(result["delta_diversity"], 4))
        print("\nThis is causal instrumentation, not an interpretation of what the form 'is'.")
    input("\nEnter to return.")

# ─────────────────────────────────────────────────────────────────────────────
# 10. BOOT / MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────

def genesis_screen():
    clear_screen()
    print("""
╭──────────────── WORLDHEART 🧫 ────────────────╮
│                                               │
│                    GENESIS                    │
│                                               │
│  No inhabitants defined.                     │
│  No objectives defined.                      │
│  No language defined.                        │
│  No fitness function defined.                │
│  No destination defined.                     │
│                                               │
│  The observer is outside the glass.           │
│                                               │
╰───────────────────────────────────────────────╯
""")

def choose_world():
    genesis_screen()
    latest = os.path.join(SAVE_DIR, SAVE_FILE)
    if os.path.exists(latest):
        ans = input("Resume preserved universe? [Y/n] ").strip().lower()
        if ans not in ("n", "no"):
            try:
                w = World.load(latest)
                print("Recovered transition", w.tick)
                time.sleep(0.6)
                return w
            except Exception as e:
                print("Recovery failed:", e)
                print("Genesis remains available.")
    raw = input("Genesis seed [%s]: " % DEFAULT_SEED).strip()
    try:
        seed = int(raw) if raw else DEFAULT_SEED
    except ValueError:
        seed = int(stable_hash(raw), 16)
    return World(seed)

def main():
    world = choose_world()
    paused = False
    render(world, paused)

    # Console-friendly batching. Press Enter to advance a batch. This works
    # reliably in Pythonista without requiring terminal-specific key capture.
    while True:
        cmd = input("\nworldheart> ").strip().lower()

        if cmd in ("q", "quit", "exit"):
            fn = world.save()
            print("Preserved:", fn)
            break
        elif cmd in ("s", "save"):
            print("Preserved:", world.save())
            continue
        elif cmd in ("p", "pause"):
            paused = not paused
            render(world, paused)
            continue
        elif cmd in ("i", "inspect"):
            inspect(world)
            render(world, paused)
            continue
        elif cmd in ("f", "fossils"):
            show_fossils(world)
            render(world, paused)
            continue
        elif cmd in ("c", "probe"):
            show_probe(world)
            render(world, paused)
            continue
        elif cmd in ("n", "named"):
            label = input("Checkpoint label: ").strip() or "checkpoint"
            print("Preserved:", world.save_named(label))
            continue
        elif cmd.startswith("run "):
            try:
                batches = max(1, min(100000, int(cmd.split()[1])))
            except Exception:
                print("Use: run <number of 120-transition batches>")
                continue
            total = batches * TICKS_PER_FRAME
        elif cmd in ("", "run", "r"):
            total = TICKS_PER_FRAME
        else:
            print("Unknown command; universe unchanged.")
            continue

        if paused:
            render(world, paused)
            continue

        started = time.time()
        try:
            for _ in range(total):
                world.transition()
        except KeyboardInterrupt:
            pass
        elapsed = max(1e-9, time.time() - started)
        render(world, paused)
        print("  %.0f transitions/sec" % (total / elapsed))

if __name__ == "__main__":
    main()
