# OrbSim — briefing for an AI assistant (math focus)

You are being briefed on a desktop program, **OrbSim** (v1.0.0), that a student uses to solve and visualise orbit-mechanics problems
(Bate–Mueller–White conventions, as taught in a university orbit-mechanics course). The student will paste or describe the program's output and ask you
to check, interpret or extend it. This file tells you **what the program computes, which equations and sign conventions it uses, what it verified itself
against, and where it stops being valid.** Treat every convention below as binding: several differ from common textbooks.

Everything is **two-body / patched-conic** analytics. There is no numerical integration, no perturbation model (J2, drag, third bodies except in the
N-body acceleration module), no ephemeris. Planets are on circular heliocentric orbits of their mean radius unless a problem says otherwise.

---

## 1. Conventions (read first)

| Item | Convention used by the program |
|---|---|
| True anomaly | $\theta^*$, measured from periapsis. Quadrant is **always** fixed with `atan2`, never `arccos` alone: $\theta^*=\operatorname{atan2}\!\big(\tfrac{\bar r\cdot\bar v}{r}\tfrac{h}{\mu},\ \tfrac{p}{r}-1\big)$. |
| Flight-path angle | $\gamma$ measured **from the local horizon**, $\gamma>0$ when $\dot r>0$: $\tan\gamma=\dfrac{e\sin\theta^*}{1+e\cos\theta^*}$. (BMW's $\varphi$ is the zenith angle: $\varphi=90^\circ-\gamma$.) |
| Argument of latitude | $\theta=\omega+\theta^*$. A problem that says "$\theta=235^\circ$" means $\theta$, **not** $\theta^*$. |
| 3-D rotation | 3-1-3 sequence $(\Omega,i,\theta)$. Columns of the DCM are $\hat r,\hat\theta,\hat h$ expressed in $\hat x,\hat y,\hat z$. |
| RAAN quadrant | $\hat h=(\sin\Omega\sin i,\,-\cos\Omega\sin i,\,\cos i)$, so $\Omega=\operatorname{atan2}(\hat h_x,-\hat h_y)$. Equatorial orbit ($i\approx0$): $\Omega$ is undefined, set to $0^\circ$ and flagged. |
| VNC frame | $\hat V=\hat v$, $\hat N=\hat h$, $\hat C=\hat V\times\hat N$ (GMAT calls it "VNB"). $\Delta\bar v=\Delta v\,(\cos\beta\cos\alpha\,\hat V+\sin\beta\,\hat N+\cos\beta\sin\alpha\,\hat C)$. |
| $\hat r\hat\theta\hat h$ form | $\Delta\bar v=\Delta v\,(\cos\beta\sin\Phi\,\hat r+\cos\beta\cos\Phi\,\hat\theta+\sin\beta\,\hat h)$, $\Phi=\alpha+\gamma$. |
| Impulse angle $\alpha$ | Measured from $\bar v^-$. **$\alpha>0$ when the impulse turns $\bar v$ away from the central body** (toward $\hat C$). HW10 also reports components on $\hat B=\hat N\times\hat V=-\hat C$. |
| Energy / direction split | $\%\text{energy}=\dfrac{|v^+-v^-|}{|\Delta\bar v|}\times100$, $\%\text{direction}=100-\%\text{energy}$. |
| Time since periapsis | Reported both as $t-t_p\in(-P/2,P/2]$ and as $0\ldots P$ (e.g. $738.2\,\text{h}=P-16.79\,\text{h}$). |
| Hyperbolic aim point | $\theta^*_{\text{aim}}=-(\theta^*_\infty-90^\circ)$ on approach; $d_{\text{aim}}=\sqrt{(r_p+|a|)^2-b^2}=|a|$. |
| Calendar | 30-day months in HW4, Julian year $=365.25$ d, JD day $=86\,400$ s, 1 AU $=149\,597\,870.7$ km. The constants table lists Earth's $a=149\,597\,898$ km: use that for "Earth's orbit radius". |
| Units | km, km·s⁻¹, km³·s⁻² for $\mu$, degrees for angles, seconds internally (results shown also in h, d, yr). |

**Constants:** only the JPL / GMAT 2020a "Useful Constants" table is used ($\mu,R,a,e$ for the Sun, Moon, planets and Pluto). Printed course answers that were worked with rounded exam constants (for example $\mu_\oplus=4.0	imes10^5$) differ from this program's values in the 4th digit, and those exam presets were removed.

---

## 2. Core relations the program implements (all verified, see §4)

**Conic geometry.** $p=\dfrac{h^2}{\mu}$, $\ e=\sqrt{1+\dfrac{2\varepsilon h^2}{\mu^2}}$, $\ a=-\dfrac{\mu}{2\varepsilon}$, $\ r=\dfrac{p}{1+e\cos\theta^*}$, $\ v=\sqrt{\mu\!\left(\tfrac2r-\tfrac1a\right)}$,
$\varepsilon=\tfrac{v^2}{2}-\tfrac{\mu}{r}$, $\ h=r\,v_\theta$, $\ r_p=\dfrac{p}{1+e}$, $\ r_a=\dfrac{p}{1-e}$, $\ P=2\pi\sqrt{a^3/\mu}$.
From a polar state $(r,v_r,v_\theta)$: $e\sin\theta^*=v_rh/\mu$, $\ e\cos\theta^*=p/r-1$.

**Kepler's equation (Newton iteration).**
Ellipse: $M=E-e\sin E$, $\ E=2\operatorname{atan2}\!\big(\sqrt{1-e}\sin\tfrac{\theta^*}{2},\sqrt{1+e}\cos\tfrac{\theta^*}{2}\big)$; start $E_0=M+e\sin M$ ($E_0=\pi$ for $e\ge0.8$).
Hyperbola: $M=e\sinh H-H$, $\ H=2\operatorname{artanh}\!\big(\sqrt{\tfrac{e-1}{e+1}}\tan\tfrac{\theta^*}{2}\big)$, $n=\sqrt{\mu/|a|^3}$.
$t-t_p=M/n$.

**$f$ and $g$ (both forms, shown to agree).**
$\Delta\theta^*$ form: $f=1-\dfrac rp(1-\cos\Delta\theta^*)$, $g=\dfrac{r\,r_0\sin\Delta\theta^*}{h}$, $\dot g=1-\dfrac{r_0}{p}(1-\cos\Delta\theta^*)$,
$\dot f=\sqrt{\tfrac\mu p}\tan\tfrac{\Delta\theta^*}{2}\Big(\tfrac{1-\cos\Delta\theta^*}{p}-\tfrac1r-\tfrac1{r_0}\Big)$,
with $r=\dfrac{p}{1+(p/r_0-1)\cos\Delta\theta^*-\sqrt{p/\mu}\,\frac{\bar r_0\cdot\bar v_0}{r_0}\sin\Delta\theta^*}$.
$\Delta E$ form (ellipse): $f=1-\dfrac a{r_0}(1-\cos\Delta E)$, $g=\Delta t-\sqrt{\tfrac{a^3}{\mu}}(\Delta E-\sin\Delta E)$, $\dot f=-\dfrac{\sqrt{\mu a}\,\sin\Delta E}{r\,r_0}$, $\dot g=1-\dfrac ar(1-\cos\Delta E)$.
Always $f\dot g-\dot f g=1$. Then $\bar r=f\bar r_0+g\bar v_0$, $\bar v=\dot f\bar r_0+\dot g\bar v_0$.

**Elements from a state.** $\bar e=\dfrac{(v^2-\mu/r)\bar r-(\bar r\cdot\bar v)\bar v}{\mu}$, $\hat h=\dfrac{\bar r\times\bar v}{h}$, $i=\arccos\hat h_z$ (unambiguous on $[0,180^\circ]$),
$\Omega$ as in §1, $\theta=\operatorname{atan2}\!\big(\hat r_z/\sin i,\ \hat r\cdot\hat n\big)$, $\omega=\theta-\theta^*$.

**Single impulse (coplanar).** At one point: $\Delta v^2=v_1^2+v_2^2-2v_1v_2\cos\Delta\gamma$, with $\alpha=\operatorname{atan2}(\Delta\bar v\cdot\hat C,\ \Delta\bar v\cdot\hat V)$.
Two coplanar orbits with a common focus ($p_1,e_1$; $p_2,e_2$; periapsis of orbit 2 rotated by $\Delta\omega$) intersect where
$A\cos\theta^*+B\sin\theta^*=C$, $\ A=p_2e_1-p_1e_2\cos\Delta\omega$, $B=-p_1e_2\sin\Delta\omega$, $C=p_1-p_2$ — **both** roots are kept, the minimum $|\Delta\bar v|$ is chosen, the other is listed.
$\theta^*_2=\theta^*_1-\Delta\omega$ at the burn. Wait time = Kepler time on the old orbit from the current $\theta^*$ to the burn point.
Given $(\Delta v,\alpha,\beta)$ in 3-D, the program applies $\Delta\bar v$ in VNC and recomputes all elements ($\Delta\omega,\Delta\Omega,\Delta i$ reported).

**Hyperbolas.** $a=-\mu/v_\infty^2$, $\ e=1+\dfrac{r_pv_\infty^2}{\mu}$, $\ \theta^*_\infty=\arccos(-1/e)$, $\ \delta=2\arcsin(1/e)$, $\ b=|a|\sqrt{e^2-1}$, $\ v_p=\sqrt{\mu(2/r_p+1/|a|)}$.
Give any two of $(r_p,|a|,e,v_\infty)$ ($|a|$ and $v_\infty$ are not independent).

**Coplanar transfers.** Hohmann: $a_T=\tfrac{r_1+r_2}{2}$, $\Delta v_1=|v_p-v_{c1}|$, $\Delta v_2=|v_{c2}-v_a|$, $\text{TOF}=\pi\sqrt{a_T^3/\mu}$, departure phase angle $\varphi=180^\circ-n_2\,\text{TOF}$,
synodic period $T_{\text{syn}}=2\pi/|n_1-n_2|$. Bi-elliptic via $r_b$: three burns, $\text{TOF}=\pi\big(\sqrt{a_1^3/\mu}+\sqrt{a_2^3/\mu}\big)$.
**Eccentric target:** arrival is at the target's perihelion/aphelion and $\Delta v_2$ uses the target's **actual speed there** $\sqrt{\mu(2/r-1/a_t)}$, not the circular speed.

**Plane change.** Rotation about the line of nodes: $\Delta v=2\,v_\theta\sin\tfrac{\Delta i}{2}$ with $v_\theta=v\cos\gamma$ (for a circular orbit: $2v\sin\tfrac{\Delta i}2$; in VNC $\alpha=180^\circ$, $\beta=90^\circ-\Delta i/2$).
Three-burn alternative (circular start): raise apoapsis to $r_a$, change plane there ($2v_a\sin\tfrac{\Delta i}2$), return; total $=2\Delta v_{\text{raise}}+\Delta v_{\text{plane}}$, $\text{TOF}=P_{\text{transfer ellipse}}$.

**Patched conics.** $\bar v_\infty=\bar v_{\text{transfer}}-\bar v_{\text{planet}}$ (a **vector** difference — non-tangential departure is handled).
Departure from a circular parking orbit: $\Delta v_{\text{dep}}=\sqrt{v_\infty^2+\tfrac{2\mu}{r_p}}-\sqrt{\tfrac\mu{r_p}}$. Capture into an orbit of eccentricity $e_c$ at periapsis $r_p$:
$\Delta v_{\text{cap}}=\sqrt{v_\infty^2+\tfrac{2\mu}{r_p}}-\sqrt{\tfrac{\mu(1+e_c)}{r_p}}$.

**Gravity assist (planar).** $e=1+\dfrac{r_pv_\infty^2}{\mu}$, $\delta=2\arcsin\tfrac1e$; $\bar v_\infty^+=R(\pm\delta)\,\bar v_\infty^-$, $\bar v^+=\bar v_{\text{pl}}+\bar v_\infty^+$.
Both senses are computed; heliocentric energy change $\Delta\varepsilon=\bar v_{\text{pl}}\cdot(\bar v_\infty^+-\bar v_\infty^-)$: **positive = energy gained = pass behind the planet**, negative = lost = pass ahead.
Equivalent heliocentric impulse $|\Delta\bar v_{\text{eq}}|=2v_\infty\sin\tfrac\delta2$ with its own $\alpha$; $\Delta\omega=\theta^*_{\text{old}}-\theta^*_{\text{new}}$ at the planet.
(For a *tangential* encounter both senses give the same $\Delta\varepsilon$ and mirror-image orbits.) Free return: transfer ellipse from $r_1$ to the planet's orbit with transfer angle TA satisfies
$p=r_1(1+e)=r_2(1+e\cos\text{TA})\Rightarrow e=\dfrac{r_2-r_1}{r_1-r_2\cos\text{TA}}$; symmetric exit $v_r^+=-v_r^-$ gives the required turn $\delta$ and $r_p=\dfrac{\mu_{\text{pl}}}{v_\infty^2}\Big(\dfrac1{\sin(\delta/2)}-1\Big)$.

**Lambert (angle-based $\alpha$–$\beta$ form, zero full revolutions).** $\text{TA}<180^\circ$ is type 1, $>180^\circ$ type 2 (use $2\pi-\text{TA}$ in the chord).
$c=\sqrt{r_1^2+r_2^2-2r_1r_2\cos\text{TA}}$, $\ s=\tfrac{r_1+r_2+c}{2}$, minimum-energy $a_m=s/2$.
$\text{TOF}_{\text{par}}=\dfrac{\sqrt2}{3\sqrt\mu}\big(s^{3/2}\mp(s-c)^{3/2}\big)$ (− type 1, + type 2): $\text{TOF}<\text{TOF}_{\text{par}}\Rightarrow$ hyperbola (types 1H/2H).
Ellipse: $\sin^2\tfrac\alpha2=\tfrac{s}{2a}$, $\sin^2\tfrac\beta2=\tfrac{s-c}{2a}$, $\ \text{TOF}=\sqrt{\tfrac{a^3}{\mu}}\big[(\alpha-\sin\alpha)\mp(\beta-\sin\beta)\big]$; $\text{TOF}<\text{TOF}_{\min}\Rightarrow$ type A, else type B ($\alpha\to2\pi-\alpha$).
Solved by bisection in $\log a$ (type A: TOF decreases with $a$; type B and hyperbolic: increases).
**Two $p$ roots** always exist: $p=\dfrac{4a(s-r_1)(s-r_2)}{c^2}\sin^2\dfrac{\alpha\pm\beta}{2}$ (sinh² for hyperbolas); the program reports both, which has the smaller $\Delta v$, and whether $r_p$ is below the surface.
Velocities: $f=1-\tfrac{r_2}{p}(1-\cos\text{TA})$, $g=\dfrac{r_1r_2\sin\text{TA}}{\sqrt{\mu p}}$, $\ \bar v_D=\dfrac{\bar r_A-f\bar r_D}{g}$, $\ \bar v_A=\dot f\bar r_D+\dot g\bar v_D$.
Burns are measured against circular prograde in-plane orbits at $r_1,r_2$ ($\Delta v_D$, $\alpha_D$, $\Delta v_A$, $\alpha_A$, components on $\hat V,\hat C,\hat B$).
Also: phase angle $\psi=\text{TA}-n_2\,\text{TOF}$, "does the arc pass periapsis?" ($\theta^*_D<0<\theta^*_D+\text{TA}$), perihelion vs body radius.
Position inputs may be 2-D radii + TA, 3-D vectors (plane normal chosen with $\hat h\cdot\hat z>0$ unless told otherwise), or RA/Dec + distance; time may be TOF, minimum energy, or a given $p$.

**N-body relative acceleration.** For body $i$ relative to central body $c$ ($\mu_j=Gm_j$, $\bar d_{ij}=\bar r_j-\bar r_i$):
$\ddot{\bar r}_{ic}=\underbrace{-\tfrac{(\mu_c+\mu_i)\bar r_{ic}}{r_{ic}^3}}_{\text{dominant}}+\underbrace{\sum_j\mu_j\tfrac{\bar d_{ij}}{d_{ij}^3}}_{\text{direct}}\ \underbrace{-\sum_j\mu_j\tfrac{\bar d_{cj}}{d_{cj}^3}}_{\text{indirect}}$ ($j\ne i,c$; set $\mu_i=0$ for a spacecraft).
Output: each term, net perturbing, total, magnitudes, ranking, perturbing/dominant ratio, barycentre.
**Two-body constants:** $\bar C_3=\bar r\times\bar v$, $C_4=\varepsilon=v^2/2-\mu/r$ (*the identification of $C_4$ with $\varepsilon$ is an assumption — check against the course notes*), $h=|\bar C_3|$, areal velocity $h/2$, barycentre velocity $\dfrac{m_1\bar v_1+m_2\bar v_2}{m_1+m_2}$; $\varepsilon=0\Rightarrow$ parabola.

---

## 3. Modules (what to ask the student for)

| # | Module | Inputs | Key outputs |
|---|---|---|---|
| 1 | N-body accelerations | $\mu_j$, positions, central + target body | dominant / direct / indirect / net / total vectors, ranking |
| 2 | Two-body constants | $m_1,m_2$ (or $\mu$ with $G=1$), $\bar r_i,\bar v_i$ | $\bar C_3$, $C_4$, $h$, areal velocity, barycentre, relative conic |
| 3 | State ⇄ planar conic | polar $(r,v_r,v_\theta)$, $xy$ state, $(h,\varepsilon)$, $(r_p,r_a)$, $(a,e)$ or $(p,e)$ | $p,e,a,P,\varepsilon,h,\gamma,\theta^*,E/H,r_p,r_a$, $\bar r,\bar v$ in $\hat r\hat\theta$ and $\hat e\hat p$ |
| 4 | Kepler propagation | $a,e$ (or $r_p,r_a$), start as $\theta^*$, $M$ or $E$, $\Delta t$ or "until $\theta^*_1$" | new $\theta^*,E,M,r,v,\gamma,t-t_p$; $f,g,\dot f,\dot g$ in both forms |
| 5 | Hyperbolic flyby geometry | two of $r_p,|a|,e,v_\infty$ | $p,e,h,\varepsilon,v_\infty,\theta^*_\infty,\delta,b,d_{\text{aim}}$, $H$, time to periapsis, capture $\Delta v$ |
| 6 | Elements ⇄ 3-D state | $(a,e,i,\Omega,\omega,\theta^*\text{ or }\theta)$ or $(\bar r,\bar v)$ | all elements with quadrant checks, vectors in $\hat r\hat\theta\hat h$, $\hat e\hat p\hat h$, $\hat x\hat y\hat z$ |
| 7 | Single impulse | old orbit + target orbit (+$\Delta\omega$) **or** $\Delta v,\alpha,\beta$ at $\theta^*$ | all intersections, min $|\Delta\bar v|$, $\alpha$, $\Delta\gamma$, %energy, new elements, $\Delta\omega$ |
| 8 | Hohmann / bi-elliptic | $r_1,r_2$, optional $r_b$, optional eccentric target | $\Delta v$'s, TOF, phase angle, synodic period |
| 9 | Plane change | orbit, $\Delta i$, optional $r_a$ | single vs three-burn $\Delta v$, TOF, $\alpha,\beta$ |
| 10 | Patched conics | transfer (Hohmann or given states), parking and capture orbits | $\bar v_\infty$ (vector, angle from planet velocity), departure/capture $\Delta v$, hyperbolas |
| 11 | Gravity assist | incoming heliocentric state, planet, $r_p$ | $\delta$, $\bar v_\infty^\pm$, new orbit, $\Delta\omega$, $\Delta v_{\text{eq}}$, energy gained/lost (both senses), free return |
| 12 | Lambert / two-position | positions + TOF / min-energy / given $p$ | type, TOF$_{\text{par}}$, TOF$_{\min}$, $a$, both $p$, $e$, $f,g,\dot f,\dot g$, $\bar v_D,\bar v_A$, burns, $\psi$, plane elements |

The program shows a **step-by-step table** (quantity, symbol, value, units, equation) and a list of **quadrant / sanity checks** it performed. When a student
pastes results, ask for that table and the checks list, and for the constants set and unit choice (km / $R_{\text{body}}$ / AU).

---

## 4. How correct is it? (verification you can rely on)

* The math core was ported from a reference implementation without changing any formula and is guarded by **173 regression checks**, plus **169 preset checks** run through
  the full application code path. Every expected value is copied from the official homework / exam solutions (HW 3–10, Fall 2024 Exams 1–2) and lecture-note examples; tolerance is relative $2\times10^{-4}$ unless the solution prints fewer digits.
* Reference values you can sanity-check against (Course table): Earth→Pluto Hohmann $\Delta v_1=11.8138$, $\Delta v_2=3.6864$ km/s, TOF $=45.5412$ yr, phase $113.9276^\circ$, synodic $1.0041$ yr;
  Venus hyperbola ($r_p=10R$, $|a|=50R$): $v_\infty=1.0361349$ km/s, $\theta^*_\infty=146.44269^\circ$, $\delta=112.88538^\circ$; Earth→Mars minimum-energy Lambert (TA $=130^\circ$): $e=0.31037$, TOF $=240.64357$ d, $v_D=32.22270$ km/s, $v_\infty=8.58217$ km/s;
  circularise $r_p=7000,r_a=45000$ km at $r=25\,000$ km: $\theta^*=134.8508^\circ$, $\Delta v=3.2098$ km/s, $\alpha=-114.7013^\circ$.
* **Known errors in the printed solutions** (the program and its tests use the corrected values):

| Where | Printed | Correct |
|---|---|---|
| HW5 P4 | $\Omega=114.80^\circ$ | $\Omega=65.20^\circ$ ($\sin\Omega\sin i=0.5538$, $-\cos\Omega\sin i=-0.2560\Rightarrow\cos\Omega>0$) |
| HW7 P3(e) | "$v_{sJ}=4.7399$" | arrival uses Pluto's perihelion speed $6.1117$ km/s; $\Delta v_2=4.7149$, total $16.3595$ are right |
| HW10 P1 | $a=5.36R_\oplus$ | $a=34\,100.93$ km $=5.3465R_\oplus$ |
| Exam 2 P2 | $h=8.7333\times10^4$, $g=3608.166$ s | with exam constants $h=\sqrt{\mu p}=8.7636\times10^4$, $g=3620.39$ s |
| Exam 2 P3 | TOF $=8.24419$ h | that used course constants; with exam constants $n=1.5441\times10^{-4}$ s⁻¹, TOF $=8.2721$ h |
| Exam 1 P3 | $P=18.877$ "da" | $18.88$ **h** |
| Lecture notes LLex 2 | TOF$_{\min}$(Phobos→Deimos) $=5.705$ h | $8.210$ h |
| Lecture notes LLex 1 | $e=0.8225$, $\Delta V_{D,y}=-3.24$ | $e=0.8825$, $-0.324$ |
| Lecture notes LA 4 | constant term $4a^2(\dots)$ | $16a^2(\dots)$ |

If your own algebra disagrees with a printed solution, check this table before concluding anyone is wrong.

---

## 5. Limits — do not over-trust the program (or yourself) beyond these

* Lambert is single-arc, **zero full revolutions** in the application (the core accepts $N$, the UI does not expose it). Hyperbolic Lambert is supported.
* Gravity assist and patched conics are **planar**; planets are on circular orbits of mean radius (no ephemeris, no eccentric planet unless the module says so, e.g. the eccentric *target* in Module 8).
* Plane-change formula $2v\cos\gamma\sin(\Delta i/2)$ is the program's own extension for non-circular orbits (identical to the textbook formula when $\gamma=0$); the three-burn option is circular-start only.
* Parabolas ($\varepsilon=0$, $e=1$): geometry and flags only; no $E/H$ or period.
* $C_4\equiv\varepsilon$ in Module 2 is an assumption about the course's notation.
* Equatorial orbits: $\Omega$ undefined, reported as $0^\circ$ (then $\omega$ is the longitude of periapsis).
* A Lambert transfer's perigee may be **below the planet's surface**; the program warns, it does not forbid. Check that warning before accepting a "solution".
* Angles are degrees in the interface, radians internally; all internal times are seconds.

---

## 6. How to help the student well

1. Ask for the **constants set**, **units**, and the **step table**; compare against §1 conventions (especially $\gamma$ from the horizon, $\theta$ vs $\theta^*$, sign of $\alpha$).
2. Reproduce one or two numbers by hand with the equations in §2 before trusting a chain of results; quote the equation used.
3. Recheck every angle's **quadrant** (the program prints the sign tests it used).
4. For a maneuver, state *why* the chosen intersection / root / sense is optimal and what the alternative costs (the program lists them).
5. For gravity assists name the pass geometry (behind = gain, ahead = lose) and the sign of $\Delta\varepsilon$.
6. Never invent expected values; if a problem is not in §4's list, derive it and say so.

Project page: <https://github.com/Chiyami1213/orbsim> · Source of truth for the math: `mathkit/core/` (verbatim reference port) and `tests/test_hw.py`.

---

## 7. Conventions, realistic models and GMAT compatibility (Mission workspace)

### 7.1 Two presentations of the same numbers

Everything in modules 1–12, the presets and the Test Cases stays in the **course convention**. A presentation switch (Settings → Conventions, or the toggle in a result header) shows the same values the GMAT way. It never changes a stored value.

| Quantity | Course | GMAT | Relation |
|---|---|---|---|
| Flight-path angle | $\gamma$ from the local horizon, $+$ when $\dot r>0$ | `HFPA` $=\gamma$; `VFPA` from the radius vector | $\mathrm{VFPA}=90^\circ-\gamma$ |
| Anomalies | $\theta^*,M,E\in(-180^\circ,180^\circ]$ | `TA`, `MA`, `EA` in $[0^\circ,360^\circ)$ | wrap |
| Impulse | $\Delta v,\alpha,\beta$ in VNC | `ImpulsiveBurn` `Element1..3` in `VNB` | $E_1=\Delta v\cos\beta\cos\alpha$, $E_2=\Delta v\sin\beta$, $E_3=\Delta v\cos\beta\sin\alpha$ ($B=V\times N=\hat C$) |
| Energy | $\varepsilon$ | `Energy`, `C3Energy` | $C_3=2\varepsilon$ |
| Bodies / dates | Moon; JD | `Luna`; `UTCModJulian` | $\mathrm{ModJulian}=\mathrm{JD}-2430000.0$ (**not** JD $-2400000.5$) |

Worked check (HW4 problem 3): $\gamma=-62.397426^\circ\Rightarrow$ `VFPA` $=152.397426^\circ$; $\theta^*_{aim}=-56.4427^\circ\Rightarrow$ `TA` $=303.5573^\circ$. The solution text's "270° offset" is really $\mathrm{VFPA}=90^\circ-\gamma$.
Constants are always the JPL / GMAT table, so a GMAT script reproduces this program's numbers.

### 7.2 Realistic models: why answers differ from the course

* **Course model:** two bodies only; analytic; planets on circular orbits of mean radius; each leg is a conic about one body.
* **Mission workspace:** state $\bar y=[\bar r,\bar v]$ integrated numerically with adaptive Runge–Kutta (Verner 8(9), Prince–Dormand 7(8)/4(5); coefficients from NASA GMAT, Apache 2.0). Third-body accelerations use the **direct + indirect** form of §2 (Module 1): $\ddot{\bar r}=-\mu_c\bar r/r^3+\sum_j\mu_j\left(\frac{\bar d_j-\bar r}{|\bar d_j-\bar r|^3}-\frac{\bar d_j}{d_j^3}\right)$.
  Optional $J_2$, cannonball radiation pressure, exponential drag. Restricted three-body: circular, nondimensional rotating frame, Jacobi constant $C_J=x^2+y^2+2(1-\mu)/r_1+2\mu/r_2-v^2$; collinear points from the standard quintics.
* **Why the answers differ:** Moon/Sun/planet perturbations change $a,e,i,\omega,\Omega$ secularly and periodically; a finite arc of a hyperbola only *approaches* $v_\infty$ and $\theta^*_\infty$ (HW4: 1.0466 km/s and 146.06° at the end of a finite arc against 1.0361 km/s and 146.44° from theory — an asymptote, not a mismatch); patched conics ignore the third body inside each sphere of influence $r_{SOI}=a(m/M)^{2/5}$ (Earth $\approx9.25\times10^5$ km).
* **Events:** periapsis ($\bar r\cdot\bar v$ rising through 0), apoapsis (falling), `TA = x` (wrap-safe), `RMAG = x`, elapsed time; located by bracketing and an Illinois root finder to $10^{-9}$ s. With several stop conditions the earliest wins.
* **Ephemerides:** built-in = Standish approximate Keplerian elements (inner planets within about $10^4$–$7\times10^4$ km, Jupiter to Pluto within a few $10^6$ km of DE440s in 2026) plus a truncated Meeus lunar theory (about 50 km); optional JPL **DE440s** (1849–2150) through `jplephem`. Time scale: UTC → TAI (leap seconds, 37 s since 2017) → TT (+32.184 s) → TDB; GMAT's A1 = TAI + 0.0343817 s.
* **Checks that must agree:** the exact Kepler solution and the numerical two-body run agree to $10^{-8}$ relative; "Open in Mission" on modules 3–8 and 12 reproduces the module numbers (HW4 problem 3: start $\theta^*=-110^\circ$, $r=225826.422$ km; aim point $\theta^*=-56.4427^\circ$, $r=80045.573$ km, $v=3.03157$ km/s).

### 7.2b The Sandbox

The Sandbox integrates every body with $\mu>0$ against every other (pairwise point-mass gravity, barycentric ICRF frame, Verner RK8(9), relative tolerance $10^{-11}$); bodies with $\mu=0$ are test particles. The real Solar System is initialised from the active ephemeris at the chosen epoch; the total-energy drift over a year is about $10^{-14}$ and Earth stays between 0.9833 and 1.0168 AU. A body's "parent" for the orbit panel is the heavier body whose Laplace sphere of influence $|\bar r_j-\bar r_{root}|(\mu_j/\mu_{root})^{2/5}$ contains it, else the heaviest body. An edit is applied at the current simulation time (the scene is first advanced there) and the simulation is re-run both ways. A spacecraft can be sent to the Design mode as a Cartesian state about its parent with the other massive bodies as point masses.

### 7.3 GMAT compatibility

* Export: GMAT R2022a script syntax (`Create Spacecraft`, `ForceModel` with `CentralBody`/`PointMasses`, `Propagator`, `CoordinateSystem`, `ImpulsiveBurn`, `ReportFile`, `OrbitView`, then `BeginMissionSequence` and `Propagate`/`Maneuver`/`Report`/`Toggle`). Module answers are written as `% expected:` comments. The Moon is `Luna`.
* GMAT's `MarsMJ2000Eq` keeps **Earth's** J2000 equator axes; the course's "Mars equatorial" frame is `BodyInertial` (Mars pole RA 317.68°, Dec 52.89°).
* Import: a subset parsed by a small tokenizer; `Target`/`Vary`/`Achieve`, GMAT functions, spherical-harmonic fields and drag models are listed as skipped. The tutorial script `Tut_SimulatingAnOrbit.script` loads and runs.
* Models GMAT does not have (analytic Kepler, restricted three-body) are exported as the closest GMAT force model with a comment.
* Not modelled: spherical-harmonic gravity, finite-burn attitude, targeting. Licence: portions derived from NASA GMAT (Apache 2.0), see `NOTICE`.
