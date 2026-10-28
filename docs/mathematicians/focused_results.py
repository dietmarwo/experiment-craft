"""Draw images/focused-results.png for the guide's derivative-root case study.

The values are the certified results that the guide reports: the lower ends of
the exact intervals for B(f), rounded for display, and the exact degree-four
hull moment with its three terms. The terms are rounded to four places as the
campaign reported them. Run with Python and matplotlib from the repository
root:

    python3 docs/mathematicians/focused_results.py
"""
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / 'images' / 'focused-results.png'
ARCS = {8: 1.535182113114249446, 16: 1.712540654859401688,
        32: 1.836600941824469776, 48: 1.887581747240161414}
CLUSTER = (17, 1.784968583232396345)
MOMENT = 1.207518862355812743
TERMS = [('d_4^{4/3}', 0.6412), ('d_3^{4/3}', 0.2827), ('d_2^{4/3}', 0.2836)]
ARC_COLOR, CLUSTER_COLOR = '#17798d', '#c8692a'
SHADES = ['#17798d', '#5aaf9c', '#b5d6b3']

plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Latin Modern Roman', 'DejaVu Serif'],
                     'mathtext.fontset': 'cm', 'font.size': 12, 'axes.spines.top': False,
                     'axes.spines.right': False})
figure, (chains, moment) = plt.subplots(1, 2, figsize=(9.0, 3.5), dpi=250,
                                        gridspec_kw={'width_ratios': [1.35, 1]})

chains.scatter(list(ARCS), list(ARCS.values()), s=70, color=ARC_COLOR, zorder=3, label='Elliptical arcs')
chains.scatter([CLUSTER[0]], [CLUSTER[1]], s=90, marker='D', color=CLUSTER_COLOR, zorder=3,
               label='Endpoint clusters')
offsets = {8: (8, 8), 16: (8, -16), 32: (8, 8), 48: (-12, 10)}
for degree, value in ARCS.items():
    chains.annotate(f'{value:.4f}', (degree, value), xytext=offsets[degree], textcoords='offset points',
                    ha='right' if degree == 48 else 'left', fontsize=12)
chains.annotate(f'{CLUSTER[1]:.4f}', CLUSTER, xytext=(-10, 6), textcoords='offset points', ha='right',
                fontsize=12)
chains.set(xlim=(4, 52), ylim=(1.45, 1.95), xticks=[8, 16, 24, 32, 40, 48], xlabel='Polynomial degree',
           ylabel='Certified $B(f)$, lower bound')
chains.set_title('Selected strict examples')
chains.grid(axis='y', color='#e6e6e6')
chains.legend(loc='lower right', frameon=False, fontsize=11)

bottom = 0.0
for (label, value), shade in zip(TERMS, SHADES):
    moment.bar([0], [value], bottom=bottom, width=0.6, color=shade, edgecolor='white', linewidth=1.5)
    moment.text(0, bottom + value / 2, f'${label} = {value:.4f}$', ha='center', va='center', fontsize=12,
                color='white' if shade == SHADES[0] else '#1d2b2f')
    bottom += value
moment.axhline(1.0, color='#b23a30', linestyle='--', linewidth=1.4)
moment.text(0.95, 1.02, 'Tested $C=1$', color='#b23a30', fontsize=12, ha='right', va='bottom')
moment.text(0, MOMENT + 0.04, f'Total {MOMENT:.7f}', ha='center', va='bottom', fontsize=13, fontweight='bold')
moment.set(xlim=(-0.45, 1.0), ylim=(0, 1.4), xticks=[0], xticklabels=['Exact certificate'],
           ylabel='$M_{4/3}(f)$')
moment.set_title('Hull moment, degree 4')
moment.grid(axis='y', color='#e6e6e6')
moment.set_axisbelow(True)
chains.set_axisbelow(True)

figure.tight_layout()
figure.savefig(OUTPUT)
print(OUTPUT)
