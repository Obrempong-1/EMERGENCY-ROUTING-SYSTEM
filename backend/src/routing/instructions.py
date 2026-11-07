"""Turn-by-turn instructions derived from a traversed edge sequence.

Edges are first turned into manoeuvres (what the traveller does at each
junction), then into text. Keeping the two apart lets roundabouts and road
changes be recognised before any wording is chosen.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, radians, sin
from typing import Optional

from .graph import haversine_m

_STRAIGHT_DEG = 20.0
_SLIGHT_DEG = 45.0
_SHARP_DEG = 120.0
_UTURN_DEG = 160.0

TURN_AROUND_DEG = 150.0

_CONNECTOR_MAX_M = 40.0

_BEARING_SPAN_M = 20.0

_COMPASS = ("north", "north-east", "east", "south-east",
            "south", "south-west", "west", "north-west")

@dataclass
class Manoeuvre:
    """What happens on entering `edges[0]`, and the edges it covers."""

    kind: str
    phrase: str
    edges: list
    exit_number: Optional[int] = None

def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing from point 1 to point 2, in degrees from north."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_lambda = radians(lon2 - lon1)
    y = sin(d_lambda) * cos(phi2)
    x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(d_lambda)
    return (degrees(atan2(y, x)) + 360.0) % 360.0

def build_instructions(edges: list, destination_name: Optional[str] = None,
                       graph=None, mode_bit: Optional[int] = None,
                       heading: Optional[float] = None, offset_m: float = 0.0) -> list:
    """Group edges into steps of {text, kind, distance_m, road, location, at_m}.

    With `graph` and `mode_bit`, roundabout steps name the exit to take and a bend
    with no other way on is not announced as a turn. With `heading`, the
    traveller's direction of travel in degrees, the first step says which way to
    turn, or to turn around, instead of only a compass point. `location` is where
    a step's manoeuvre happens and `at_m` how far along the route that is,
    counting `offset_m` of approach before the first edge.
    """
    if not edges:
        return []

    names = _effective_names(edges)
    steps = []
    travelled = offset_m
    for manoeuvre in _manoeuvres(edges, names, graph, mode_bit, heading):
        step = _step(manoeuvre)
        start = manoeuvre.edges[0].geometry[0]
        step["location"] = [start[0], start[1]]
        step["at_m"] = round(travelled, 1)
        travelled += sum(edge.length_m for edge in manoeuvre.edges)
        steps.append(step)

    end = edges[-1].geometry[-1]
    steps.append({
        "text": f"Arrive at {destination_name}" if destination_name else "Arrive at your destination",
        "kind": "arrive",
        "distance_m": 0,
        "road": steps[-1]["road"],
        "location": [end[0], end[1]],
        "at_m": round(travelled, 1),
    })
    return steps

def heading_change(heading: float, edge) -> float:
    """Signed degrees from a direction of travel onto an edge: negative is left."""
    return _signed_turn(heading, _entry_bearing(edge))

def _manoeuvres(edges: list, names: list, graph, mode_bit, heading) -> list:
    """Detect and classify each manoeuvre along the route."""
    found = [_departure(edges[0], heading)]
    index = 1

    while index < len(edges):
        previous, edge = edges[index - 1], edges[index]

        if edge.roundabout and not previous.roundabout:
            end = index
            while end + 1 < len(edges) and edges[end + 1].roundabout:
                end += 1
            ring = edges[index:end + 1]
            exit_edge = edges[end + 1] if end + 1 < len(edges) else None
            covered = ring + ([exit_edge] if exit_edge is not None else [])
            found.append(Manoeuvre(
                kind="roundabout",
                phrase="At the roundabout,",
                edges=covered,
                exit_number=_exit_number(ring, graph, mode_bit) if exit_edge else None,
            ))
            index = end + 2
            continue

        phrase, kind = _classify(_signed_turn(_exit_bearing(previous), _entry_bearing(edge)))
        if kind not in ("straight", "uturn") and not _is_choice(previous, edge, graph, mode_bit):
            kind = "straight"
        current = found[-1]
        if kind == "straight" and not current.edges[-1].roundabout and _same_road(
                current.edges[-1], edge, names[index - 1], names[index]):
            current.edges.append(edge)
        elif kind == "straight":
            found.append(Manoeuvre(kind="continue", phrase="Continue onto", edges=[edge]))
        else:
            found.append(Manoeuvre(kind=kind, phrase=f"{phrase} onto", edges=[edge]))
        index += 1

    return found

def _departure(edge, heading: Optional[float]) -> Manoeuvre:
    """The first step, turned relative to the traveller when their heading is known."""
    compass = _compass_point(_entry_bearing(edge))
    if heading is not None:
        turn = heading_change(heading, edge)
        if abs(turn) >= TURN_AROUND_DEG:
            return Manoeuvre(kind="uturn", phrase=f"Turn around and head {compass} on",
                             edges=[edge])
        if abs(turn) >= _SLIGHT_DEG:
            phrase, kind = _classify(turn)
            return Manoeuvre(kind=kind, phrase=f"{phrase} onto", edges=[edge])
    return Manoeuvre(kind="depart", phrase=f"Head {compass} on", edges=[edge])

def _is_choice(previous, edge, graph, mode_bit) -> bool:
    """Whether the junction offers more than one way on.

    Where the road is the only way forward, a bend there is not a turn anyone can
    get wrong, so it is not announced as one. Going back the way the traveller
    came is not an option. Without a graph every junction counts as a choice.
    """
    if graph is None or mode_bit is None:
        return True
    arriving = _exit_bearing(previous)
    ways_on = 0
    for out in graph.neighbours(edge.from_node):
        if not out.allowed & mode_bit or out.to_node == previous.from_node:
            continue
        if abs(_signed_turn(arriving, _entry_bearing(out))) >= _UTURN_DEG:
            continue
        ways_on += 1
    return ways_on > 1

def _step(manoeuvre: Manoeuvre) -> dict:
    last = manoeuvre.edges[-1]
    road = _road_label(last)
    distance = sum(edge.length_m for edge in manoeuvre.edges)

    if manoeuvre.kind == "roundabout":
        if last.roundabout:
            text = "Enter the roundabout"
        elif manoeuvre.exit_number:
            text = f"At the roundabout, take the {_ordinal(manoeuvre.exit_number)} exit onto {road}"
        else:
            text = f"At the roundabout, exit onto {road}"
    else:
        text = f"{manoeuvre.phrase} {road}"

    return {
        "text": f"{text} for {_format_distance(distance)}",
        "kind": manoeuvre.kind,
        "distance_m": round(distance),
        "road": road,
    }

def _effective_names(edges: list) -> list:
    """Edge names, with a short unnamed connector taking the road it links.

    A few metres of unnamed way between two stretches of the same named road,
    crossed without turning, is part of that road to the traveller.
    """
    names = [edge.name or "" for edge in edges]
    for i in range(1, len(edges) - 1):
        edge = edges[i]
        if names[i] or edge.length_m > _CONNECTOR_MAX_M:
            continue
        before, after = names[i - 1], names[i + 1]
        if not before or before != after:
            continue
        into = _signed_turn(_exit_bearing(edges[i - 1]), _entry_bearing(edge))
        out = _signed_turn(_exit_bearing(edge), _entry_bearing(edges[i + 1]))
        if abs(into) < _STRAIGHT_DEG and abs(out) < _STRAIGHT_DEG:
            names[i] = before
    return names

def _same_road(previous, edge, previous_name: str, name: str) -> bool:
    """Named roads match by name; unnamed ones only if they are the same kind."""
    if previous_name or name:
        return previous_name == name
    return previous.highway == edge.highway

def _exit_number(ring: list, graph, mode_bit) -> Optional[int]:
    """Which exit leaves the roundabout: exits passed on the way, plus one.

    An exit is a road the traveller could legally leave by: an outgoing,
    non-roundabout edge open to the mode. Each such road counts, so two roads
    leaving from one node are two exits; entry-only one-ways are not exits.
    """
    if graph is None or mode_bit is None:
        return None
    passed = 0
    for edge in ring[:-1]:
        passed += len({out.to_node for out in graph.neighbours(edge.to_node)
                       if not out.roundabout and out.allowed & mode_bit})
    return passed + 1

def _signed_turn(from_bearing: float, to_bearing: float) -> float:
    return (to_bearing - from_bearing + 540.0) % 360.0 - 180.0

def _classify(turn: float) -> tuple[str, str]:
    magnitude = abs(turn)
    side = "left" if turn < 0 else "right"
    if magnitude >= _UTURN_DEG:
        return "Make a U-turn", "uturn"
    if magnitude >= _SHARP_DEG:
        return f"Turn sharp {side}", f"sharp-{side}"
    if magnitude >= _SLIGHT_DEG:
        return f"Turn {side}", f"turn-{side}"
    if magnitude >= _STRAIGHT_DEG:
        return f"Bear {side}", f"slight-{side}"
    return "Continue straight", "straight"

def _entry_bearing(edge) -> float:
    start = edge.geometry[0]
    ahead = _point_along(edge.geometry)
    if ahead == start:
        return 0.0
    return bearing(start[0], start[1], ahead[0], ahead[1])

def _exit_bearing(edge) -> float:
    end = edge.geometry[-1]
    behind = _point_along(tuple(reversed(edge.geometry)))
    if behind == end:
        return 0.0
    return bearing(behind[0], behind[1], end[0], end[1])

def _point_along(points, span_m: float = _BEARING_SPAN_M) -> tuple:
    """The point `span_m` along a polyline, or its far end when it is shorter.

    A road's direction at a junction is read over this stretch rather than from
    its last vertex pair, so a few metres of kink or overshoot in the OSM drawing
    cannot flip a left turn into a right one.
    """
    travelled = 0.0
    for a, b in zip(points, points[1:]):
        step = haversine_m(a[0], a[1], b[0], b[1])
        if step > 0 and travelled + step >= span_m:
            share = (span_m - travelled) / step
            return (a[0] + (b[0] - a[0]) * share, a[1] + (b[1] - a[1]) * share)
        travelled += step
    return points[-1]

def _road_label(edge) -> str:
    if edge.name:
        return edge.name
    descriptor = edge.highway.replace("_", " ").strip()
    return f"the {descriptor}" if descriptor else "the road"

def _ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"

def _compass_point(degrees_from_north: float) -> str:
    return _COMPASS[int((degrees_from_north + 22.5) % 360.0 // 45.0)]

def _format_distance(metres: float) -> str:
    if metres < 1000.0:
        if metres < 20.0:
            return f"{max(int(round(metres)), 1)} m"
        return f"{int(round(metres / 10.0) * 10)} m"
    return f"{metres / 1000.0:.1f} km"
