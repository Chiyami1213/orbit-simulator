# Build prompt: AAE 532 Orbit Toolkit (Python, 3D animation + calculator)

Paste this whole file into Claude in VS Code. Put `orbitcore.py` and `test_hw.py` (shipped with this prompt) in the project root first.

---

## 0. Goal

Build a local Python app, **AAE 532 Orbit Toolkit**, that solves every recurring problem type from Purdue AAE 532 (Orbit Mechanics, Bate–Mueller–White textbook) and visualizes it:

- an annotated **2D figure** in the style required for homework (Cartesian, not polar),
- an interactive, animated **3D view**,
- a **step-by-step results table** that shows the intermediate values graders look for.

Platform: Windows 11, VS Code, Python 3.11+. Stack: **NumPy**, **SciPy** (optional), **matplotlib** (2D figures), **Plotly** (3D and animation), **Streamlit** (UI). Run with `streamlit run app.py`.

## 1. Non-negotiable: the math is already verified

`orbitcore.py` is a **verified reference implementation**. It was cross-checked against:

- the course lecture notes (Lec 1–43),
- Bate, Mueller & White (§1.10, §2.3–2.5, §3.3–3.4, §4.2–4.6, §5, §7.4, §8.3),
- the numbers in the HW 1–10 and Fall 2024 Exam 1–2 solutions.

`test_hw.py` runs **173 checks**, and all of them pass. Each expected value is copied from a solution PDF.

Rules:
1. Port `orbitcore.py` into the package (`aae532/core/…`) **without changing any formula**. Refactor names and structure as you like, but keep behavior identical.
2. Convert `test_hw.py` to pytest (`tests/test_hw.py`). It must pass at every commit. Add a test for every new function.
3. If you think a formula is wrong, **do not "fix" it silently**. Write a failing test that cites the source and stop to ask.
4. Never use `arccos` alone for an angle that has a quadrant. Use `atan2` or an explicit sign test (on ṙ, ẑ, etc.), and show the quadrant check in the step output.

## 2. Conventions (course notes; these differ from some textbooks)

| Item | Convention |
|---|---|
| Flight-path angle γ | from the local horizon; γ > 0 when ṙ > 0. `tan γ = e sin θ*/(1+e cos θ*)`. (BMW's φ is the zenith angle: φ = 90° − γ.) |
| θ | **argument of latitude** θ = ω + θ*. Problems give "θ = 235°" meaning θ, not θ*. |
| 3D rotation | 3-1-3 (Ω, i, θ); the columns of `dcm_313` are r̂, θ̂, ĥ expressed in x̂, ŷ, ẑ |
| Ω quadrant | ĥ = (sinΩ sin i, −cosΩ sin i, cos i) → `Ω = atan2(ĥx, −ĥy)`. Equatorial orbit: Ω undefined → set 0 and say so |
| VNC frame | V̂ = v̂, N̂ = ĥ, Ĉ = V̂ × N̂ (GMAT calls this "VNB"). Δv̄ = Δv(cosβ cosα V̂ + sinβ N̂ + cosβ sinα Ĉ) |
| r̂θ̂ĥ impulse | Δv̄ = Δv(cosβ sinΦ r̂ + cosβ cosΦ θ̂ + sinβ ĥ), Φ = α + γ |
| α sign | measured from v̄⁻; **α > 0 when the impulse turns v̄ away from the central body** (toward Ĉ); negative when toward the body. HW10 also reports components on B̂ = N̂ × V̂ (= −Ĉ) |
| % energy / % direction | %energy = \|v⁺ − v⁻\| / \|Δv̄\| × 100; %direction = 100 − %energy (HW6 P2) |
| Time since periapsis | report both t − t_p ∈ (−P/2, P/2] **and** 0…P (HW5 P3 uses 738.2 h = P − 16.79 h) |
| Aim point (hyperbola) | θ*_aim = −(θ*_∞ − 90°) on approach; d_aim = √((r_p + \|a\|)² − b²) = \|a\| |
| Months, years | HW4 uses 30-day months; Julian year = 365.25 d; JD day = 86 400 s |
| AU | 149 597 870.7 km (reproduces the HW4 numbers). The constants table lists Earth's a = 149 597 898 km; use the table value for "Earth's orbit radius" |

## 3. Constants

There are two switchable sets, shown in the top bar as **"Course table"** and **"Exam rounded"**:

- **Course table:** the `BODIES` dict in `orbitcore.py`, i.e. the course "Useful Constants" table (GMAT 2020a / JPL). It holds μ, R, a and e for the Sun, Moon, planets and Pluto.
- **Exam rounded:** μ⊕ = 4.0×10⁵ (km³·s⁻²), R⊕ = 6400 (km); Moon μ = 5000, R = 2000 on Exam 1 and **1500** on Exam 2; Mars μ = 4.2×10⁴, R = 3400. Let the user edit the Moon radius.

Output units must be shown in parentheses with a center dot, e.g. (km·s⁻¹), (km²·s⁻²), (km³·s⁻²). Angles in degrees. Allow distances in km, R_body, or AU.

## 4. Modules (one Streamlit page or tab each)

Each module returns a `Result` object holding: the inputs echoed back, every intermediate value (name, symbol, value, units, equation used), the quadrant checks performed, warnings (e.g. "perigee below surface", "orbit hyperbolic"), and the plot specs. The UI renders the same object in three views: table, 2D, 3D.

| # | Module | Inputs | Outputs | 2D figure must mark |
|---|---|---|---|---|
| 1 | N-body accelerations (HW2 P1–2, HW3 P1, Exam 1 P1) | bodies with μ and position (collinear, triangle, or free 2D/3D); choose central body and target | dominant, direct, indirect, net perturbing and total acceleration vectors and magnitudes; ranking; perturbing/dominant ratio; center of mass | arrow per term, unit vectors, center of mass |
| 2 | Two-body constants (HW2 P3, HW3 P3, Exam 1 P3) | masses, states | C̄₃, C₄, h, ε, areal velocity, center-of-mass velocity; ε = 0 → parabola case | center of mass, both paths |
| 3 | State ⇄ planar conic | r with (ṙ, rθ̇), or r̄, v̄ in ê/p̂, or (h, ε), or (r_p, r_a), etc. | p, e, a, P, ε, h, γ, θ*, E or H, r_p, r_a; r̄, v̄ in r̂θ̂ and êp̂ | conic, ê/p̂, line of apsides, minor axis, r̄, v̄, θ*, γ, **local horizon**, foci |
| 4 | Kepler propagation | elements + θ*₀ or M₀ or E₀, Δt | new θ*, E, M, r, v, γ, t − t_p; f, g, ḟ, ġ in **both** Δθ* and ΔE forms (show they agree); plot of r vs θ*, E, M | **auxiliary circle**, E, Δθ*, ΔE, arc from t₀ to t₁ |
| 5 | Hyperbolic flyby geometry | any two of r_p, \|a\|, e, v∞, or a state | p, e, h, ε, v∞, θ*_∞, δ, b, d_aim, aim point, H, time to periapsis, v_p, capture Δv to circular or eccentric orbit | asymptotes, aim point, b, δ, θ*_∞, p, r_p, ±120° arc |
| 6 | Elements ⇄ 3D state | a, e, i, Ω, ω, θ* (or θ) ⇄ r̄, v̄ in x̂ŷẑ | all elements, quadrant checks, M, E, t − t_p; vectors in r̂θ̂ĥ, êp̂ĥ, x̂ŷẑ | 3D: orbit, equatorial plane, line of nodes, ascending/descending nodes, i, Ω, ω, both triads |
| 7 | Single-impulse maneuver (HW6 P2, HW7 P1–2, Exam 2 P1) | (a) target orbit (r_p, r_a or e, Δω, circularize at r) → **all** intersection points, pick min \|Δv̄\| and show the others; (b) given Δv, α, β at θ* → new orbit | v̄⁻, γ⁻, v̄⁺, γ⁺, Δv, α (sign), Δγ, %energy/%direction, new elements, Δω, wait time from current position; VNC, r̂θ̂ĥ, êp̂ĥ components | old and new orbits, **velocity triangle**, local horizon, Δv̄, α, Δω, new line of apsides |
| 8 | Coplanar transfers and rendezvous (HW7 P3, HW8 P2, HW10 P2a, P3a) | r₁, r₂, optional r_b; optional eccentric target (arrive at perihelion using the **target's actual speed there**) | Hohmann and bi-elliptic Δv's, TOF, transfer angle, phase angle at departure, synodic period | transfer arcs; animation with both bodies moving so the phase angle is visible |
| 9 | Plane change (HW8 P3, HW11 P2) | v (or orbit), Δi; optional bi-elliptic with r_a | single-burn vs three-burn cost and TOF | 3D planes before and after, velocity triangle at the node |
| 10 | Patched conics (HW8 P4, HW9 P2a, HW10 P3d) | heliocentric (or Earth-centered) transfer + parking and capture orbits | v̄∞ (vector, including **non-tangential departure**), departure and arrival Δv, capture into circular or eccentric orbit at periapsis | heliocentric view + planet-centered hyperbola inset |
| 11 | Gravity assist (HW8 P4c, HW9 P2b–P4) | v̄⁻ (from a transfer arc), planet velocity, r_p, pass sense | δ, v̄∞±, v̄⁺, γ⁺, new orbit (a, e, r_p, r_a, P, ε, θ*⁺), Δω, Δv̄_eq (magnitude and α), **energy gained or lost**; free return (TA given, symmetric v_r⁺ = −v_r⁻) → required r_p and altitude | vector triangle, old and new orbits, planet-frame hyperbola with asymptotes |
| 12 | Lambert and two-position problems (HW10 P1–3, HW11, Exam 2 P2) | r₁, r₂ as 2D radii + TA, 3D vectors, or RA/Dec + distance; plus TOF (general), minimum energy, or given p | type 1A/1B/2A/2B/1H/2H, TOF_par, TOF_min, a, both p roots, e, ε, f, g, ḟ, ġ, v̄_D, v̄_A, γ, θ* at both ends, Δv_D, α_D, Δv_A, α_A (VNC too), total, phase angle ψ = TA − n₂·TOF, "passes periapsis?", transfer i, Ω, ω (choose ĥ·ẑ > 0 unless told otherwise), perihelion check vs a body radius | transfer arc, **vacant focus F**, departure and arrival orbits, burns, local horizons |

Utilities: Julian date ⇄ calendar (include time of day; HW8/HW9 P1 ask for "Friday 9:30 am ET" → convert ET to UT), a constants browser, and a **Test cases** page. The test page loads each HW/exam problem as a preset and shows the expected value next to the computed one.

## 5. Algorithms to keep exactly as in `orbitcore.py`

- **Kepler:** Newton on E − e sin E = M. Start at E₀ = M + e sin M, or E₀ = π for e ≥ 0.8. Hyperbolic: e sinh H − H = M. Use the half-angle `atan2` forms for E⇄θ* and `arctanh`/`tanh` forms for H⇄θ*.
- **f and g:** the Δθ* form (`fg_theta`) and the ΔE form (`fg_E`, BMW 4.6-29…32).
- **Elements from r̄, v̄:** ē = ((v² − μ/r) r̄ − (r̄·v̄) v̄)/μ. θ* from `atan2((r̄·v̄/r)·h/μ, p/r − 1)`. θ from r̂_z/sin i and the in-plane component. ω = θ − θ*. Handle i ≈ 0.
- **Impulse in plane:** `impulse_planar(v1, γ1, v2, γ2)`. It gives the cosine law plus α as `atan2` of the C and V components.
- **Orbit intersections:** `intersect_conics(p1, e1, p2, e2, Δω)` solves A cos θ* + B sin θ* = C and returns both crossings.
- **Lambert:** the notes' α–β form. Type 1 if TA < 180°, type 2 if TA > 180°.
  - TOF_par (Euler): s^{3/2} ∓ (s − c)^{3/2}.
  - TOF_min uses α = π.
  - TOF < TOF_par → hyperbolic. TOF < TOF_min → type A, otherwise B.
  - Bisect in log a. Type A: TOF decreases with a. Type B and hyperbolic: TOF increases with a.
  - p roots: `4a(s − r₁)(s − r₂)/c² · sin²((α ± β)/2)`, with sinh² for hyperbolas.
  - Velocities from f and g. Always offer **both roots** and report which has the smaller Δv and whether r_p is below the surface.
- **Minimum energy:** a = s/2, single p (`lambert_minE`).
- **Flyby:** δ = 2 asin(1/e), e = 1 + r_p v∞²/μ. Rotate v̄∞⁻ by ±δ. Compute both senses and label each "energy gained" or "energy lost". The rule: passing behind the planet gains energy, passing ahead loses it.
- **Patched conics:** Δv_dep = √(v∞² + 2μ/r_p) − √(μ/r_p). Capture into an eccentric orbit: √(v∞² + 2μ/r_p) − √(μ(1 + e)/r_p).

## 6. Plot specification

Create one reusable annotation layer (matplotlib for 2D, Plotly for 3D) with functions:
`local_horizon`, `vector(r̄|v̄|Δv̄)`, `angle_arc(γ|θ*|α|δ|E|Δω)`, `apsides_line`, `minor_axis`, `unit_triad(ê,p̂ | r̂,θ̂ | x̂,ŷ,ẑ)`, `aux_circle`, `asymptotes`, `aim_point_b`, `vacant_focus`, `nodes_line`, `equatorial_plane`.

- Every figure title includes the user's name (an editable setting; HW instructions require it) and the problem label.
- Equal axis scaling and Cartesian axes. Never use polar axes.
- Label collision avoidance: offset labels radially from the focus and never let text overlap lines or other labels. Verify this visually for each module's preset.
- Export PNG/PDF at 300 dpi for submission.
- 3D view:
  - rotate, zoom, and preset view buttons (orbit-normal, along line of nodes, isometric);
  - auto-rotate toggle;
  - **play/pause with a speed slider (0.1×–10×)** and a time scrubber;
  - a legend;
  - a readout of t, r, v, γ, θ* while animating;
  - animation frames placed by solving Kepler's equation, so they are uniform in time, not in angle.
- Dark and light themes.

## 7. Structure

```
aae532/
  core/          constants.py  conic.py  kepler.py  fg.py  frames.py  elements.py  hyperbola.py
                 maneuvers.py  transfers.py  patched.py  flyby.py  lambert.py  nbody.py  timeutil.py
  results.py     Result/Step dataclasses (name, symbol, value, units, equation, note)
  plots2d/       annotate.py + one figure function per module
  view3d/        scene.py (Plotly), animate.py
  presets/       hw_problems.py (every HW/exam problem as an input preset + expected values)
app.py           Streamlit entry; sidebar = modules; top bar = constants switch, units, theme, name
tests/           test_hw.py (from the shipped file) + unit tests per module
```

## 8. Build order and acceptance criteria

1. Core package + `pytest` green (all 173 checks).
2. Modules 3 → 4 → 6 → 7 → 12, each with its preset problems, 2D figure, 3D view, and step table.
3. Modules 8, 10, 11, 5, then 1, 2, 9; then utilities.
4. For each module: load its presets, compare against the expected values (rtol 2e-4 unless the solution prints fewer digits), screenshot the 2D figure, and check for label overlaps.
5. The final 3D animations must run smoothly. The speed slider must change playback speed, not jump frames.

## 9. Known errors in the solution PDFs (the toolkit's tests use the corrected values)

| Where | Printed | Correct | Evidence |
|---|---|---|---|
| HW5 P4 | Ω = 114.80° | **Ω = 65.20°** | sinΩ sin i = 0.5538 and −cosΩ sin i = −0.2560 give cosΩ > 0. Round-trip elements → r̄, v̄ reproduces the given state only with 65.20°. θ, ω, i are unaffected. |
| HW7 P3(e) | "v_sJ = 4.7399" in the perihelion case | the arrival Δv uses Pluto's **perihelion speed**, 6.1117 (km·s⁻¹) | the printed Δv₂ = 4.7149 and total 16.3595 are right; only the label/value line is wrong |
| HW10 P1 | a = 5.36 R⊕ | a = 34 100.93 km = **5.3465 R⊕** | the km value printed alongside is right |
| Exam 2 P2 | h = 8.7333×10⁴, g = 3608.166 s | with exam constants h = √(μp) = 8.7636×10⁴, g = 3620.39 s | v̄₁ agrees to 4 digits either way |
| Exam 2 P3 | TOF = 8.24419 h | 8.24419 h uses course constants for n. With the exam's rounded constants, n = 1.5441×10⁻⁴ and **TOF = 8.2721 h** | the toolkit should show both when "Exam rounded" is on |
| Exam 1 P3 | P = 18.877 days… (printed as "18.877 da") | P = 18.88 **h** (a = 5R_♂ exactly gives 18.877 h) | unit label |
| Lecture notes LLex 2 | TOF_min(Phobos→Deimos) = 5.705 h | 8.210 h | Kepler's equation along the 240° arc |
| Lecture notes LLex 1 | e = 0.8225; ΔV_D,y = −3.24 | e = 0.8825; −0.324 | |
| Lecture notes LA 4 | constant term 4a²(…) | 16a²(…) | the roots satisfy the quadratic only with 16 |

## 10. Style

- Clear docstrings that cite the lecture-note page or BMW equation number.
- Type hints throughout.
- No silent unit conversions: carry units in names (`r_km`, `v_kms`, `t_s`).
- Format every displayed number with its units in parentheses.
