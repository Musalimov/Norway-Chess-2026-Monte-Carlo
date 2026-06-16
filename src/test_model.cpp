// Unit tests for the Norway Chess probability model (src/model.hpp).
// Pure-math tests, no I/O, no simulation. Builds to a binary in bin/.
//
// Build: g++ -O2 -std=c++17 src/test_model.cpp -o bin/test_model
// Run:   ./bin/test_model   (exit 0 = all pass)

#include <cstdio>
#include <cmath>
#include <string>
#include "model.hpp"

static int failures = 0;
static int checks = 0;

static void check(const std::string& name, bool ok) {
    ++checks;
    printf("  [%s] %s\n", ok ? "PASS" : "FAIL", name.c_str());
    if (!ok) ++failures;
}
static bool approx(double a, double b, double tol = 1e-9) { return std::fabs(a - b) < tol; }

int main() {
    using namespace nc;
    ModelParams m{35.0, 0.70, 0.0018, -30.0, 32.0, 0.85, 0.01};

    printf("== Elo expectation ==\n");
    check("equal ratings -> 0.5", approx(elo_expect(0.0), 0.5));
    check("+400 Elo -> ~0.909", approx(elo_expect(400.0), 1.0/(1.0+0.1), 1e-9));
    check("monotonic: +100 > equal", elo_expect(100.0) > elo_expect(0.0));
    check("antisymmetry: e(d)+e(-d)=1", approx(elo_expect(123.0)+elo_expect(-123.0), 1.0));

    printf("== Classical probabilities ==\n");
    double pw, pd, pb;
    classical_probs(m, 2800, 2700, 1.0, 1.0, pw, pd, pb);
    check("W/D/L sum to 1", approx(pw + pd + pb, 1.0, 1e-12));
    check("all non-negative", pw >= 0 && pd >= 0 && pb >= 0);
    check("stronger+white player favoured (pw>pb)", pw > pb);

    // symmetry: equal players, no white edge -> pw == pb
    ModelParams m0 = m; m0.wa = 0.0;
    classical_probs(m0, 2750, 2750, 1.0, 1.0, pw, pd, pb);
    check("equal players, no white edge -> pw==pb", approx(pw, pb, 1e-12));

    // white advantage increases white's share
    double pw_adv, pd_adv, pb_adv, pw_noadv, pd_noadv, pb_noadv;
    classical_probs(m,  2750, 2750, 1.0, 1.0, pw_adv, pd_adv, pb_adv);
    classical_probs(m0, 2750, 2750, 1.0, 1.0, pw_noadv, pd_noadv, pb_noadv);
    check("white advantage raises pw", pw_adv > pw_noadv);

    // higher style multiplier -> more draws
    double pwA,pdA,pbA, pwB,pdB,pbB;
    classical_probs(m, 2750, 2750, 1.0, 1.0, pwA,pdA,pbA);
    classical_probs(m, 2750, 2750, 1.3, 1.3, pwB,pdB,pbB);
    check("higher style -> higher draw prob", pdB > pdA);

    // draw cap respected for very drawish equal players
    ModelParams mcap = m; mcap.dbase = 2.0; // force cap
    classical_probs(mcap, 2750, 2750, 1.0, 1.0, pw, pd, pb);
    check("draw probability capped at dcap", pd <= m.dcap + 1e-9);

    // huge gap: weaker side floored at minp, still sums to 1
    classical_probs(m, 3200, 2400, 1.0, 1.0, pw, pd, pb);
    check("huge favourite: loser prob floored >= minp", pb >= m.minp - 1e-12);
    check("huge favourite: still sums to 1", approx(pw + pd + pb, 1.0, 1e-12));

    printf("== Armageddon ==\n");
    // Convention: armh<0 means White is favoured (historically White wins ~56%).
    double a_eq = armageddon_white_prob(m, 2750, 2750);
    check("equal strength, armh=-30: White favoured (>0.5)", a_eq > 0.5);
    check("equal strength matches elo_expect(+30)", approx(a_eq, elo_expect(30.0)));
    double a_strong = armageddon_white_prob(m, 2900, 2700);
    check("strong white even more favoured", a_strong > a_eq);
    check("armageddon monotonic in strength", armageddon_white_prob(m, 2800,2700) > armageddon_white_prob(m, 2700,2700));
    ModelParams mh0 = m; mh0.armh = 0.0;
    check("zero handicap, equal -> 0.5", approx(armageddon_white_prob(mh0, 2750,2750), 0.5));
    ModelParams mhp = m; mhp.armh = 60.0;
    check("positive handicap favours Black (<0.5)", armageddon_white_prob(mhp, 2750,2750) < 0.5);

    printf("\n%s (%d checks, %d failed)\n",
           failures == 0 ? "ALL PASS" : "FAILURES", checks, failures);
    return failures == 0 ? 0 : 1;
}
