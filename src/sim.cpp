// Norway Chess Monte Carlo — data-driven engine.
// Reads tournament + model params from stdin (flat format from
// tools/make_sim_input.py). No hardcoded players, ratings, schedule, params;
// no JSON dependency. C++ answers only "how to simulate".
//
// Build: g++ -O2 -std=c++17 src/sim.cpp -o sim
// Run:   python3 tools/make_sim_input.py <tournament.json> <config.json> \
//          | ./sim <mode> <iters> <seed> <after_round>
//   mode: full | timeline ; after_round: condition on real rounds 1..k (full only)

#include <cstdio>
#include <cstdint>
#include <cmath>
#include <random>
#include <vector>
#include <string>
#include <iostream>
#include <algorithm>
#include "model.hpp"

struct Params { double wa, dbase, ddec, armh, k, dcap, minp; };
struct Player { double eff0, arm, style; std::string name; };
struct Game   { int p1, p2, color_known, actual; };

static Params PARS;
static std::vector<Player> PL;
static std::vector<std::vector<Game>> RND;

static inline double expect(double d){ return nc::elo_expect(d); }
static inline nc::ModelParams mp(){ return {PARS.wa,PARS.dbase,PARS.ddec,PARS.armh,PARS.k,PARS.dcap,PARS.minp}; }

static void read_input() {
    std::string tag;
    std::cin >> tag >> PARS.wa >> PARS.dbase >> PARS.ddec >> PARS.armh >> PARS.k >> PARS.dcap >> PARS.minp;
    int n; std::cin >> tag >> n;
    PL.resize(n);
    for (auto& p : PL) std::cin >> p.eff0 >> p.arm >> p.style >> p.name;
    int R; std::cin >> tag >> R;
    RND.resize(R);
    for (int r = 0; r < R; ++r) {
        int g; std::cin >> tag >> g;
        RND[r].resize(g);
        for (auto& gm : RND[r]) std::cin >> gm.p1 >> gm.p2 >> gm.color_known >> gm.actual;
    }
}

static void classical_probs(double ew, double eb, double sw, double sb,
                            double& pw, double& pd, double& pb) {
    nc::classical_probs(mp(), ew, eb, sw, sb, pw, pd, pb);
}

static void apply_actual(const Game& g, std::vector<double>& eff, std::vector<double>& pts) {
    int a = g.p1, b = g.p2;
    double e1;
    if (g.color_known) e1 = expect(eff[a] - eff[b] + PARS.wa);
    else e1 = 0.5 * (expect(eff[a]-eff[b]+PARS.wa) + expect(eff[a]-eff[b]-PARS.wa));
    double s1;
    switch (g.actual) {
        case 0: pts[a]+=3.0;              s1=1.0; break;
        case 1: pts[a]+=1.5; pts[b]+=1.0; s1=0.5; break;
        case 2: pts[a]+=1.0; pts[b]+=1.5; s1=0.5; break;
        default:pts[b]+=3.0;              s1=0.0; break;
    }
    eff[a] += PARS.k * (s1 - e1);
    eff[b] -= PARS.k * (s1 - e1);
}

static void sim_game(const Game& g, std::vector<double>& eff, std::vector<double>& pts,
                     std::mt19937_64& rng, std::uniform_real_distribution<double>& U) {
    int a = g.p1, b = g.p2, w = a, bl = b;
    if (!g.color_known && U(rng) < 0.5) { w = b; bl = a; }
    double pw, pd, pb;
    classical_probs(eff[w], eff[bl], PL[w].style, PL[bl].style, pw, pd, pb);
    double e = expect(eff[w] - eff[bl] + PARS.wa);
    double r = U(rng), Sw;
    if (r < pw) { pts[w]+=3.0; Sw=1.0; }
    else if (r < pw + pd) {
        double parm = nc::armageddon_white_prob(mp(), PL[w].arm, PL[bl].arm);
        if (U(rng) < parm) { pts[w]+=1.5; pts[bl]+=1.0; } else { pts[w]+=1.0; pts[bl]+=1.5; }
        Sw = 0.5;
    } else { pts[bl]+=3.0; Sw=0.0; }
    eff[w]  += PARS.k * (Sw - e);
    eff[bl] -= PARS.k * (Sw - e);
}

static int run_once(int after_round, std::mt19937_64& rng,
                    std::uniform_real_distribution<double>& U, std::vector<double>& pts_out) {
    int n = PL.size();
    std::vector<double> eff(n), pts(n, 0.0);
    for (int i = 0; i < n; ++i) eff[i] = PL[i].eff0;
    for (size_t r = 0; r < RND.size(); ++r)
        for (auto& g : RND[r]) {
            if ((int)r < after_round) apply_actual(g, eff, pts);
            else                      sim_game(g, eff, pts, rng, U);
        }
    std::vector<int> order(n); for (int i=0;i<n;++i) order[i]=i;
    std::sort(order.begin(), order.end(), [&](int x,int y){return pts[x]>pts[y];});
    int t=1; while (t<n && pts[order[t]]==pts[order[0]]) ++t;
    int champ = order[0];
    for (int i=1;i<t;++i)
        if (U(rng) >= expect(PL[champ].arm - PL[order[i]].arm)) champ = order[i];
    pts_out = pts;
    return champ;
}

static void run_full(int after_round, long long iters, uint64_t seed) {
    std::mt19937_64 rng(seed);
    std::uniform_real_distribution<double> U(0.0,1.0);
    int n = PL.size();
    std::vector<long long> wins(n,0);
    std::vector<std::vector<long long>> rank(n, std::vector<long long>(n,0));
    std::vector<double> psum(n,0.0), pts;
    for (long long it=0; it<iters; ++it) {
        int champ = run_once(after_round, rng, U, pts);
        wins[champ]++;
        std::vector<int> order(n); for (int i=0;i<n;++i) order[i]=i;
        std::sort(order.begin(), order.end(), [&](int x,int y){return pts[x]>pts[y];});
        for (int i=0;i<n;++i){ psum[order[i]]+=pts[order[i]]; rank[order[i]][i]++; }
    }
    printf("{\n  \"after_round\": %d,\n  \"iterations\": %lld,\n  \"players\": [\n", after_round, iters);
    for (int p=0;p<n;++p) {
        printf("    {\"name\": \"%s\", \"p_win\": %.5f, \"expected_points\": %.3f, \"rank_dist\": [",
               PL[p].name.c_str(), (double)wins[p]/iters, psum[p]/iters);
        for (int rk=0;rk<n;++rk) printf("%.5f%s",(double)rank[p][rk]/iters, rk<n-1?", ":"");
        printf("]}%s\n", p<n-1?",":"");
    }
    printf("  ]\n}\n");
}

static void run_timeline(long long iters, uint64_t seed) {
    int n = PL.size(), R = RND.size();
    printf("{ \"iterations\": %lld, \"checkpoints\": [\n", iters);
    for (int cp=0; cp<=R; ++cp) {
        std::mt19937_64 rng(seed);
        std::uniform_real_distribution<double> U(0.0,1.0);
        std::vector<long long> wins(n,0);
        std::vector<double> psum(n,0.0), pts;
        std::vector<double> effA(n), ptsA(n,0.0);
        for (int i=0;i<n;++i) effA[i]=PL[i].eff0;
        for (int r=0;r<cp;++r) for (auto& g: RND[r]) apply_actual(g, effA, ptsA);
        for (long long it=0; it<iters; ++it) { int c=run_once(cp,rng,U,pts); wins[c]++; for(int i=0;i<n;++i) psum[i]+=pts[i]; }
        printf("  {\"after_round\": %d, \"p_win\": {", cp);
        for (int p=0;p<n;++p) printf("\"%s\": %.5f%s", PL[p].name.c_str(), (double)wins[p]/iters, p<n-1?", ":"");
        printf("}, \"e_pts\": {");
        for (int p=0;p<n;++p) printf("\"%s\": %.3f%s", PL[p].name.c_str(), psum[p]/iters, p<n-1?", ":"");
        printf("}, \"actual_pts\": {");
        for (int p=0;p<n;++p) printf("\"%s\": %.1f%s", PL[p].name.c_str(), ptsA[p], p<n-1?", ":"");
        printf("}}%s\n", cp<R?",":"");
    }
    printf("]}\n");
}

int main(int argc, char** argv) {
    std::string mode = (argc>1)? argv[1] : "full";
    long long iters  = (argc>2)? atoll(argv[2]) : 1000000LL;
    uint64_t  seed   = (argc>3)? strtoull(argv[3],nullptr,10) : 20260525ULL;
    int after_round  = (argc>4)? atoi(argv[4]) : 0;
    read_input();
    if (mode == "timeline") run_timeline(iters, seed);
    else                    run_full(after_round, iters, seed);
    return 0;
}
