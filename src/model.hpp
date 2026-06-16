// Norway Chess Monte Carlo — pure probability model.
// Header-only, no I/O, no globals: shared by the engine (sim.cpp) and the
// unit-test binary (test_model.cpp) so the math is tested exactly as run.
#ifndef NC_MODEL_HPP
#define NC_MODEL_HPP
#include <cmath>
#include <algorithm>

namespace nc {

struct ModelParams {
    double wa;     // white advantage (Elo)
    double dbase;  // peak draw probability
    double ddec;   // draw decay per Elo of |diff|
    double armh;   // armageddon handicap to White (Elo)
    double k;      // form update factor
    double dcap;   // draw probability cap
    double minp;   // min outcome probability (clip)
};

// Elo expected score for a rating difference.
inline double elo_expect(double diff) {
    return 1.0 / (1.0 + std::pow(10.0, -diff / 400.0));
}

// Classical White/Draw/Black probabilities (White perspective).
// Writes pw, pd, pb; guaranteed pw+pd+pb == 1 and each >= minp (within fp).
inline void classical_probs(const ModelParams& m,
                            double eff_white, double eff_black,
                            double style_white, double style_black,
                            double& pw, double& pd, double& pb) {
    double diff = eff_white - eff_black + m.wa;
    double e = elo_expect(diff);
    pd = std::min(m.dbase * std::exp(-std::abs(diff) * m.ddec) * style_white * style_black, m.dcap);
    pw = e - pd / 2.0; if (pw < m.minp) pw = m.minp;
    pb = 1.0 - pw - pd; if (pb < m.minp) pb = m.minp;
    pd = 1.0 - pw - pb;
}

// Probability that White wins the armageddon mini-match, from armageddon
// strength ratings and the handicap to White.
inline double armageddon_white_prob(const ModelParams& m, double arm_white, double arm_black) {
    return elo_expect(arm_white - arm_black - m.armh);
}

} // namespace nc
#endif
