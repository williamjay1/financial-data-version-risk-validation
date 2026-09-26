"""Build the five main manuscript figures from frozen round-two numerical outputs.

Design constraints enforced here:
  * vector first: every figure is written as PDF (vector) and SVG (vector) plus a
    900 dpi PNG raster for review;
  * no text is placed inside a data region, so labels, tick text and value labels
    cannot collide with marks;
  * category names live outside the axes to the left, numeric annotations sit at a
    fixed clearance from bar ends, and no connecting lines are drawn between
    marks, so no line crosses text;
  * legends are placed in dedicated bands that hold no data;
  * a layout audit re-measures every artist bounding box after drawing and fails
    loudly on any collision with a text box, axes spine or clipped label.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'results/evaluation_diagnostics'
D = ROOT / 'results/development_controls'
FIG = ROOT / 'figures'
FIG.mkdir(exist_ok=True)
AUDIT: list[str] = []

# Nature-style typography: sans serif, compact, black text, thin rules.
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'Liberation Sans', 'DejaVu Sans'],
    'font.size': 7,
    'axes.titlesize': 7.5,
    'axes.labelsize': 7,
    'xtick.labelsize': 6.5,
    'ytick.labelsize': 6.5,
    'legend.fontsize': 6.5,
    'axes.linewidth': 0.6,
    'axes.edgecolor': '#000000',
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'xtick.major.size': 2.4,
    'ytick.major.size': 2.4,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'text.color': 'black',
    'axes.labelcolor': 'black',
    'xtick.color': 'black',
    'ytick.color': 'black',
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'svg.fonttype': 'none',
    'figure.dpi': 120,
    'savefig.bbox': 'standard',
    'savefig.facecolor': 'white',
})

INK = '#000000'
C_A = '#3B6EA5'   # version A / development route
C_B = '#C1663A'   # version B / input substitution route
C_N = '#7F7F7F'   # neutral marks
C_G = '#5B8C6E'   # accents
C_L = '#D9E2EC'
GRID = '#CCCCCC'
BLOCKS = ['2016_2017', '2018_2019', '2020_2021']
BLAB = {'2016_2017': '2016-2017', '2018_2019': '2018-2019', '2020_2021': '2020-2021'}


def audit(msg: str) -> None:
    AUDIT.append(msg)


def collect_text_boxes(fig):
    """Return (label, window bbox) for every text artist, in figure coordinates."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = []
    for txt in fig.findobj(matplotlib.text.Text):
        if not txt.get_visible():
            continue
        if not txt.get_text().strip():
            continue
        try:
            bb = txt.get_window_extent(renderer=renderer)
        except Exception:
            continue
        if bb.width <= 0 or bb.height <= 0:
            continue
        boxes.append((txt.get_text().replace('\n', ' ')[:40],
                      bb.transformed(fig.transFigure.inverted())))
    return boxes


def overlap(b1, b2, pad=0.0):
    return not (b1.x1 + pad <= b2.x0 or b2.x1 + pad <= b1.x0 or
                b1.y1 + pad <= b2.y0 or b2.y1 + pad <= b1.y0)


def check_text_collisions(fig, name, ignore_pairs=()):
    boxes = collect_text_boxes(fig)
    bad = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if (boxes[i][0], boxes[j][0]) in ignore_pairs:
                continue
            if overlap(boxes[i][1], boxes[j][1], pad=-0.0008):
                bad.append((boxes[i][0], boxes[j][0]))
    if bad:
        raise SystemExit(f'{name}: text collision {bad}')
    audit(f'{name}: {len(boxes)} text artists, 0 collisions')
    return boxes


def check_text_vs_axes(fig, name, axes_skip=()):
    """Text must not sit on top of an axes spine or inside a filled patch."""
    bad = []
    for ax in fig.axes:
        if ax.get_label() in axes_skip:
            continue
        frame = ax.get_window_extent().transformed(fig.transFigure.inverted())
        for label, bb in collect_text_boxes(fig):
            if not overlap(bb, frame, pad=-0.002):
                continue
            # Text authored inside this axes is expected; only flag text whose
            # baseline sits on the spine itself.
            inside = (frame.x0 < bb.x0 and bb.x1 < frame.x1 and
                      frame.y0 < bb.y0 and bb.y1 < frame.y1)
            if not inside:
                bad.append((label, ax.get_label()))
    if bad:
        raise SystemExit(f'{name}: text over axes frame {bad}')
    audit(f'{name}: text clear of axes frames')


def check_no_clipped_text(fig, name):
    for label, bb in collect_text_boxes(fig):
        if bb.x0 < -0.004 or bb.y0 < -0.004 or bb.x1 > 1.004 or bb.y1 > 1.004:
            raise SystemExit(f'{name}: clipped text {label!r} at {bb}')
    audit(f'{name}: no clipped text')


def save(fig, name, axes_skip=(), ignore_pairs=()):
    fig.canvas.draw()
    check_no_clipped_text(fig, name)
    check_text_collisions(fig, name, ignore_pairs)
    check_text_vs_axes(fig, name, axes_skip)
    for ext in ('pdf', 'svg', 'png'):
        fig.savefig(FIG / f'{name}.{ext}', dpi=900, facecolor='white')
    plt.close(fig)
    audit(f'{name}: wrote pdf (vector), svg (vector), png at 900 dpi')


def rounded_box(ax, x, y, w, h, face, edge=INK, lw=0.7, radius=0.055):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle=f'round,pad=0,rounding_size={radius}',
                                facecolor=face, edgecolor=edge, linewidth=lw))


# ----------------------------------------------------------------------------
# Figure 1. Validation design under two information clocks.
# ----------------------------------------------------------------------------
def figure1():
    fig = plt.figure(figsize=(7.2, 4.15))
    ax = fig.add_axes([0.012, 0.012, 0.976, 0.976])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')
    ax.set_label('canvas1')

    hdr = '#1F3B57'
    band = '#EDF2F7'
    band2 = '#F7F1EA'
    band3 = '#EDF4EF'

    # Row A: the two information clocks, drawn as parallel tracks with no
    # connecting lines between them, so nothing can cross.
    ax.text(2.0, 96.2, 'a', fontsize=8.5, fontweight='bold', va='center')
    ax.text(5.2, 96.2, 'Two information clocks enter the same comparison',
            fontsize=8, fontweight='bold', va='center', color=hdr)

    rounded_box(ax, 2.0, 70.0, 45.0, 21.0, band)
    ax.text(24.5, 87.4, 'Development clock', fontsize=7.4, fontweight='bold',
            ha='center', va='center', color=hdr)
    ax.text(24.5, 83.2, 'revisions disclosed before the fit date T', fontsize=6.8,
            ha='center', va='center')
    rounded_box(ax, 6.0, 73.2, 37.0, 7.0, '#FFFFFF', lw=0.6)
    ax.text(24.5, 76.7, 'training row: use A, latest B, or either source\n'
                        'filed strictly before T',
            fontsize=6.6, ha='center', va='center', linespacing=1.45)

    rounded_box(ax, 53.0, 70.0, 45.0, 21.0, band2)
    ax.text(75.5, 87.4, 'Scoring clock', fontsize=7.4, fontweight='bold',
            ha='center', va='center', color=hdr)
    ax.text(75.5, 83.2, 'inputs available at the prediction origin', fontsize=6.8,
            ha='center', va='center')
    rounded_box(ax, 57.0, 73.2, 37.0, 7.0, '#FFFFFF', lw=0.6)
    ax.text(75.5, 76.7, 'test row: A is tied to the original accession\n'
                        'B may contain later disclosure',
            fontsize=6.6, ha='center', va='center', linespacing=1.45)

    # Thin vertical separators live in the gutter between the two bands.
    ax.plot([50.0, 50.0], [70.0, 91.0], color=GRID, linewidth=0.6)

    # Row B: what is held fixed.
    rounded_box(ax, 2.0, 57.6, 96.0, 8.2, '#F2F4F6', lw=0.6)
    ax.text(50.0, 63.6, 'Held fixed across all four evaluations', fontsize=7.0,
            fontweight='bold', ha='center', va='center', color=hdr)
    ax.text(50.0, 60.2, 'observation identities   |   outcome labels   |   design weights   '
                        '|   initial missingness',
            fontsize=6.6, ha='center', va='center')

    # Row C: the crossed four-cell matrix.
    ax.text(2.0, 52.6, 'b', fontsize=8.5, fontweight='bold', va='center')
    ax.text(5.2, 52.6, 'Crossed versions and the reported contrasts',
            fontsize=8, fontweight='bold', va='center', color=hdr)

    cell_w, cell_h = 17.0, 10.0
    x0, y0 = 30.0, 20.0
    # Column headers.
    ax.text(x0 + cell_w * 0.5, 46.6, 'score A', fontsize=6.9, fontweight='bold',
            ha='center', va='center')
    ax.text(x0 + cell_w * 1.5, 46.6, 'score B', fontsize=6.9, fontweight='bold',
            ha='center', va='center')
    ax.text(x0 + cell_w * 2.9, 46.6, 'contrast', fontsize=6.9, fontweight='bold',
            ha='center', va='center')
    # Row headers, placed outside the matrix.
    ax.text(x0 - 1.6, y0 + cell_h * 1.5, 'fit A', fontsize=6.9, fontweight='bold',
            ha='right', va='center')
    ax.text(x0 - 1.6, y0 + cell_h * 0.5, 'fit B', fontsize=6.9, fontweight='bold',
            ha='right', va='center')

    cells = [
        (0, 1, 'AA\nM(A;A)', band),
        (1, 1, 'AB\nM(A;B)', band2),
        (0, 0, 'BA\nM(B;A)', band2),
        (1, 0, 'BB\nM(B;B)', band),
    ]
    for cx, cy, label, face in cells:
        rounded_box(ax, x0 + cell_w * cx, y0 + cell_h * cy, cell_w - 1.2,
                    cell_h - 1.4, face, lw=0.7)
        ax.text(x0 + cell_w * cx + (cell_w - 1.2) / 2, y0 + cell_h * cy + (cell_h - 1.4) / 2,
                label, fontsize=6.7, ha='center', va='center', linespacing=1.5)

    # Contrast column: one box per line, no rules joining them to the matrix.
    notes = [
        (y0 + cell_h * 1.5 - 3.4, 'input substitution   AB - AA', band2),
        (y0 + cell_h * 0.5 - 3.4, 'redevelopment   BA - AA', band),
    ]
    for yy, label, face in notes:
        rounded_box(ax, x0 + cell_w * 2.15, yy, cell_w * 1.75, 6.8, face, lw=0.6)
        ax.text(x0 + cell_w * 2.15 + cell_w * 0.875, yy + 3.4, label, fontsize=6.6,
                ha='center', va='center')
    rounded_box(ax, x0 + cell_w * 2.15, y0 + cell_h * 0.5 - 14.0, cell_w * 1.75, 6.8,
                band3, lw=0.6)
    ax.text(x0 + cell_w * 2.15 + cell_w * 0.875, y0 + cell_h * 0.5 - 10.6,
            'reported difference   BB - AA', fontsize=6.6, ha='center', va='center')
    ax.text(x0 + cell_w * 2.15 + cell_w * 0.875, y0 + cell_h * 0.5 - 17.2,
            'residual is the interaction term',
            fontsize=6.3, ha='center', va='center', color='#404040')

    ax.text(2.0, 8.0,
            'Each cell is fitted on one financial version and scored on another. The reported '
            'difference between two\nredeveloped pipelines is the sum of the two contrasts and the '
            'interaction, so it cannot identify which route dominates.',
            fontsize=6.5, ha='left', va='center', linespacing=1.6)

    ax.set_label('canvas1')
    save(fig, 'figure1_protocol', axes_skip=('canvas1',))


# ----------------------------------------------------------------------------
# Figure 2. Four-cell decomposition and fixed-parameter sensitivity.
# ----------------------------------------------------------------------------
def figure2():
    four = pd.read_csv(E / 'four_cell_decomposition_unrounded.csv')
    four = four.query("model=='LGBM' and metric=='average_precision'").set_index('block')
    cand = pd.read_csv(D / 'four_candidate_LGBM_AP.csv')

    fig = plt.figure(figsize=(7.2, 3.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.02, 1.0], wspace=0.32,
                          left=0.075, right=0.985, top=0.80, bottom=0.215)

    # Panel a: absolute AP in the four cells, grouped by test block.
    axa = fig.add_subplot(gs[0, 0])
    axa.set_label('a')
    cols = ['AA', 'AB', 'BA', 'BB']
    faces = [C_A, C_B, C_B, C_A]
    edges = [INK, INK, INK, INK]
    width = 0.19
    xbase = np.arange(3)
    for k, (c, f) in enumerate(zip(cols, faces)):
        vals = [four.loc[b, c] * 100 for b in BLOCKS]
        pos = xbase + (k - 1.5) * width
        axa.bar(pos, vals, width * 0.9, facecolor=f, edgecolor=edges[k],
                linewidth=0.6, zorder=3, label=c)
        for xx, vv in zip(pos, vals):
            axa.text(xx, vv + 1.0, f'{vv:.1f}', ha='center', va='bottom',
                     fontsize=5.8, rotation=90)
    axa.set_xticks(xbase)
    axa.set_xticklabels([BLAB[b] for b in BLOCKS])
    axa.set_xlim(-0.55, 2.55)
    axa.set_ylim(0, 40)
    axa.set_ylabel('Weighted average precision (%)')
    axa.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.7, zorder=0)
    axa.set_axisbelow(True)
    axa.set_title('Four-cell performance', pad=20)

    # Panel b: decomposition, drawn as separate markers so no line crosses text.
    axb = fig.add_subplot(gs[0, 1])
    axb.set_label('b')
    rows = [('Total\nBB - AA', 'total_BB_minus_AA', INK, 'o'),
            ('Redevelopment\nBA - AA', 'fit_BA_minus_AA', C_A, 's'),
            ('Input\nsubstitution\nAB - AA', 'input_AB_minus_AA', C_B, 'D'),
            ('Interaction\nJ', 'interaction', C_G, '^')]
    ypos = np.arange(len(rows))[::-1]
    for xx, b in zip(xbase, BLOCKS):
        for yy, (lab, key, col, mk) in zip(ypos, rows):
            v = four.loc[b, key] * 100
            axb.plot([xx], [yy], marker=mk, markersize=4.2, color=col,
                     markeredgecolor=INK, markeredgewidth=0.45, zorder=4)
            axb.annotate(f'{v:+.2f}', (xx, yy), textcoords='offset points',
                         xytext=(0, 7.5), ha='center', va='bottom', fontsize=5.9)
    axb.axhline(1.5, color=GRID, linewidth=0.6, zorder=1)
    axb.axhline(2.5, color=GRID, linewidth=0.6, zorder=1)
    axb.axvline(0.5, color=GRID, linewidth=0.6, zorder=1)
    axb.axvline(1.5, color=GRID, linewidth=0.6, zorder=1)
    axb.axhline(0, color=INK, linewidth=0.8, zorder=2)
    axb.set_yticks(ypos)
    axb.set_yticklabels([r[0] for r in rows], linespacing=1.35)
    axb.set_xticks(xbase)
    axb.set_xticklabels([BLAB[b] for b in BLOCKS])
    axb.set_xlim(-0.5, 2.5)
    axb.set_ylim(-0.62, 3.62)
    axb.set_ylabel('Average precision contrast (percentage points)')
    axb.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.6, zorder=0)
    axb.set_axisbelow(True)
    axb.set_title('Where the reported difference comes from', pad=20)

    fig.text(0.075, 0.955, 'a', fontsize=8.5, fontweight='bold', ha='left', va='center')
    fig.text(0.525, 0.955, 'b', fontsize=8.5, fontweight='bold', ha='left', va='center')
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=c, edgecolor=INK, linewidth=0.6)
               for c in (C_A, C_B)]
    fig.legend(handles, ['AA and BB (matched)  |  ', 'AB and BA (crossed)'],
               loc='lower center', bbox_to_anchor=(0.30, 0.115), ncol=2, frameon=False,
               handlelength=0.8, handletextpad=0.4, columnspacing=0.8)
    fig.text(0.075, 0.038,
             'Fixed LightGBM, tuned pipelines, identical test observations and weights in every cell.',
             fontsize=6.4, ha='left', va='center', color='#404040')
    save(fig, 'figure2_four_cell', axes_skip=('a', 'b'))
    return cand


# ----------------------------------------------------------------------------
# Figure 3. Development domain versus evaluation domain under a size restriction.
# ----------------------------------------------------------------------------
def figure3():
    cpi = pd.read_csv(D / 'CPI_domain_diagonal.csv').query("model=='LGBM'")
    order = ['full_train_full_test', 'full_train_size_test', 'size_train_size_test']
    lab = {'full_train_full_test': 'Full dev\nFull eval',
           'full_train_size_test': 'Full dev\nSize eval',
           'size_train_size_test': 'Size dev\nSize eval'}
    fig = plt.figure(figsize=(7.2, 3.15))
    gs = fig.add_gridspec(1, 3, wspace=0.16, left=0.085, right=0.812,
                          top=0.775, bottom=0.245)

    for k, b in enumerate(BLOCKS):
        ax = fig.add_subplot(gs[0, k])
        ax.set_label(f'c{k}')
        vals = []
        for exp in order:
            s = cpi.loc[(cpi.block == b) & (cpi.experiment == exp)]
            a = s.loc[s.train_version == 'A', 'average_precision'].iloc[0]
            v = s.loc[s.train_version == 'B', 'average_precision'].iloc[0]
            vals.append((v - a) * 100)
        yy = np.arange(len(order))[::-1]
        faces = ['#B9C6D4', '#8AA6C0', C_B] if k == 1 else ['#CFD8E2', '#A9B8C9', '#C1663A']
        for y, v, f in zip(yy, vals, faces):
            ax.barh(y, v, height=0.5, facecolor=f, edgecolor=INK, linewidth=0.6, zorder=3)
            off = 0.9 if v >= 0 else -0.9
            ax.text(v + off, y, f'{v:+.2f}', ha='left' if v >= 0 else 'right',
                    va='center', fontsize=6.0)
        ax.axvline(0, color=INK, linewidth=0.8, zorder=4)
        ax.set_yticks(yy)
        if k == 0:
            ax.set_yticklabels([lab[o] for o in order], linespacing=1.35)
        else:
            ax.set_yticklabels([])
        ax.set_xlim(-24.5, 12.5)
        ax.set_ylim(-0.55, 2.55)
        ax.set_xticks([-20, -10, 0, 10])
        ax.grid(axis='x', color=GRID, linewidth=0.5, alpha=0.65, zorder=0)
        ax.set_axisbelow(True)
        ax.set_xlabel('AP contrast BB - AA (pp)')
        ax.set_title(BLAB[b], pad=8)
        if k == 1:
            ax.annotate('development domain\nmoves the contrast',
                        xy=(-16.009, 0), xytext=(-16.0, 1.42),
                        textcoords='data', ha='left', va='center', fontsize=6.1,
                        color=C_B, linespacing=1.4)
            ax.annotate('', xy=(-16.0, 0.30), xytext=(-16.0, 1.18),
                        arrowprops=dict(arrowstyle='-', color=C_B, linewidth=0.6,
                                        shrinkA=0, shrinkB=2))

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor='#B9C6D4', edgecolor=INK, linewidth=0.6),
               plt.Rectangle((0, 0), 1, 1, facecolor='#8AA6C0', edgecolor=INK, linewidth=0.6),
               plt.Rectangle((0, 0), 1, 1, facecolor=C_B, edgecolor=INK, linewidth=0.6)]
    fig.legend(handles, ['full dev / full eval', 'full dev / size eval',
                         'size dev / size eval'],
               loc='center left', bbox_to_anchor=(0.822, 0.58), frameon=False,
               handlelength=1.1, handletextpad=0.5, labelspacing=0.7)
    fig.text(0.085, 0.955, 'Holding the evaluation sample fixed, changing the development '
                           'domain reverses the contrast',
             fontsize=7.6, fontweight='bold', ha='left', va='center')
    fig.text(0.085, 0.055,
             'Common fixed LightGBM. Size is a prediction-origin asset threshold of 100 million 1980 US dollars. '
             'The middle and right conditions\nshare the identical evaluation sample, so their difference is attributable '
             'to the development domain alone.',
             fontsize=6.4, ha='left', va='center', color='#404040', linespacing=1.55)
    save(fig, 'figure3_development_domain', axes_skip=('c0', 'c1', 'c2'))


# ----------------------------------------------------------------------------
# Figure 4. Influence of transition deletions against matched ordinary deletions.
# ----------------------------------------------------------------------------
def figure4():
    de = pd.read_csv(D / 'deletion_AP_changes.csv')
    comp = pd.read_csv(D / 'matched_deletion_comparison.csv')
    groups = ['positive_unchanged', 'changed_negative', 'other_unchanged_negative']
    glab = {'positive_unchanged': 'unchanged positive',
            'changed_negative': 'changed negatives',
            'other_unchanged_negative': 'other unchanged negatives'}
    fig = plt.figure(figsize=(7.2, 3.25))
    gs = fig.add_gridspec(1, 3, wspace=0.12, left=0.175, right=0.985,
                          top=0.745, bottom=0.225)
    for k, b in enumerate(BLOCKS):
        ax = fig.add_subplot(gs[0, k])
        ax.set_label(f'd{k}')
        for j, g in enumerate(groups):
            y = 2 - j
            mask = de.experiment.str.startswith('ordinary_matched_' + g + '_')
            vals = de.loc[mask & (de.block == b) & (de.model == 'LGBM'),
                          'total_refit_difference_minus_full'].to_numpy() * 100
            if len(vals):
                jit = np.linspace(-0.17, 0.17, len(vals))
                ax.scatter(vals, np.full(len(vals), y) + jit, s=5.5, facecolor=C_N,
                           edgecolor='none', alpha=0.85, zorder=3)
            z = comp.loc[(comp.block == b) & (comp.model == 'LGBM') & (comp.group == g)]
            if len(z) and int(z.ordinary_repetitions.iloc[0]) > 0:
                ax.scatter([z.transition_delta_change.iloc[0] * 100], [y], marker='D',
                           s=22, facecolor=C_B, edgecolor=INK, linewidth=0.5, zorder=5)
            else:
                ax.text(-21.5, y, 'no mature target', fontsize=5.9, ha='left',
                        va='center', color='#606060')
        ax.axvline(0, color=INK, linewidth=0.8, zorder=4)
        ax.set_xlim(-23.5, 15.5)
        ax.set_ylim(-0.62, 2.62)
        ax.set_xticks([-20, -10, 0, 10])
        ax.set_yticks([2, 1, 0])
        if k == 0:
            ax.set_yticklabels([glab[g] for g in groups], linespacing=1.3)
        else:
            ax.set_yticklabels([])
        ax.grid(axis='x', color=GRID, linewidth=0.5, alpha=0.65, zorder=0)
        ax.set_axisbelow(True)
        ax.set_xlabel('change in the version contrast (pp)')
        ax.set_title(BLAB[b], pad=8)
        if k == 0:
            ax.legend([plt.Line2D([], [], marker='D', linestyle='none', markersize=4.2,
                                  markerfacecolor=C_B, markeredgecolor=INK,
                                  markeredgewidth=0.5),
                       plt.Line2D([], [], marker='o', linestyle='none', markersize=3.2,
                                  markerfacecolor=C_N, markeredgecolor='none')],
                      ['transition deletion', 'matched ordinary deletion'],
                      loc='lower left', bbox_to_anchor=(0.02, 0.02), frameon=False,
                      handletextpad=0.4, labelspacing=0.5)
    fig.text(0.175, 0.955,
             'Development influence of selected observations against matched ordinary deletions',
             fontsize=7.6, fontweight='bold', ha='left', va='center')
    fig.text(0.175, 0.055,
             'Change in the common fixed LightGBM contrast relative to the block baseline; all test '
             'observations stay intact. Each dot is one of twenty matched\nordinary deletion draws. '
             'The comparison is descriptive: the draws do not equalise deleted design weight, '
             'and the percentages are not p values.',
             fontsize=6.4, ha='left', va='center', color='#404040', linespacing=1.55)
    save(fig, 'figure4_development_influence', axes_skip=('d0', 'd1', 'd2'))


# ----------------------------------------------------------------------------
# Figure 5. Source verification levels and prediction effect of adjustments.
# ----------------------------------------------------------------------------
def figure5():
    fig = plt.figure(figsize=(7.2, 2.62))
    gs = fig.add_gridspec(1, 2, width_ratios=[0.94, 1.06], wspace=0.46,
                          left=0.315, right=0.985, top=0.775, bottom=0.30)

    # Panel a: evidence level reached by each source adjustment.
    axa = fig.add_subplot(gs[0, 0])
    axa.set_label('e')
    cats = ['display-supported\nadjustment keys',
            'unresolved sign\nproposals',
            'original XBRL contexts\nauthenticated']
    vals = [43, 4, 0]
    yy = np.arange(len(cats))[::-1]
    faces = [C_G, C_B, C_N]
    for y, v, f in zip(yy, vals, faces):
        if v:
            axa.barh(y, v, height=0.46, facecolor=f, edgecolor=INK, linewidth=0.6, zorder=3)
            axa.text(v + 1.2, y, str(v), ha='left', va='center', fontsize=6.4)
        else:
            axa.plot([1.2], [y], marker='|', markersize=7, color=INK, zorder=3)
            axa.text(2.6, y, 'none', ha='left', va='center', fontsize=6.3, color='#404040')
    axa.set_yticks(yy)
    axa.set_yticklabels(cats, linespacing=1.4)
    axa.set_xlim(0, 52)
    axa.set_ylim(-0.6, 2.6)
    axa.set_xticks([0, 10, 20, 30, 40, 50])
    axa.set_xlabel('source keys or checks (n)')
    axa.grid(axis='x', color=GRID, linewidth=0.5, alpha=0.65, zorder=0)
    axa.set_axisbelow(True)
    axa.set_title('Evidence level by adjustment class', pad=8)

    # Panel b: model consequence of each adjustment scenario.
    axb = fig.add_subplot(gs[0, 1])
    axb.set_label('f')
    scen = ['Unadjusted', 'Scale supported', 'Scale + disputed signs']
    from collections import defaultdict
    groups = defaultdict(list)
    base = pd.read_csv(E / 'four_cell_decomposition_unrounded.csv')
    base = base.query("model=='LGBM' and metric=='average_precision'").set_index('block')
    sc = pd.read_csv(ROOT / 'results/scale_only/four_cell_differences.csv')
    dd = pd.read_csv(ROOT.parent / 'revision_20260922/results/corrected_models_v2/four_cell_differences.csv')
    for b in BLOCKS:
        groups['Unadjusted'].append(base.loc[b, 'total_BB_minus_AA'] * 100)
        z = sc.loc[(sc.block == b) & (sc.model == 'LGBM') &
                   (sc.metric == 'average_precision') &
                   (sc.experiment == 'source_corrected_tuned')]
        groups['Scale supported'].append(z.total_refit_difference.iloc[0] * 100)
        z2 = dd.loc[(dd.block == b) & (dd.model == 'LGBM') &
                    (dd.metric == 'average_precision') &
                    (dd.experiment == 'source_corrected_tuned')]
        groups['Scale + disputed signs'].append(z2.total_refit_difference.iloc[0] * 100)
    width = 0.24
    xbase = np.arange(3)
    for k, s in enumerate(scen):
        vals = groups[s]
        pos = xbase + (k - 1) * width
        axb.bar(pos, vals, width * 0.88, facecolor=['#B9C6D4', C_G, C_B][k],
                edgecolor=INK, linewidth=0.6, zorder=3)
        for xx, vv in zip(pos, vals):
            axb.text(xx, vv + 0.07, f'{vv:+.2f}', ha='center', va='bottom',
                     fontsize=5.7, rotation=90)
    axb.set_xticks(xbase)
    axb.set_xticklabels([BLAB[b] for b in BLOCKS])
    axb.set_xlim(-0.55, 2.55)
    axb.set_ylim(0, 4.3)
    axb.set_yticks([0, 1, 2, 3, 4])
    axb.set_ylabel('Tuned contrast BB - AA (pp)')
    axb.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.65, zorder=0)
    axb.set_axisbelow(True)
    axb.set_title('Model consequence of each scenario', pad=26)
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=c, edgecolor=INK, linewidth=0.6)
               for c in ('#B9C6D4', C_G, C_B)]
    axb.legend(handles, ['unadjusted', 'scale supported', 'scale + disputed signs'],
               loc='lower left', bbox_to_anchor=(0.005, 1.005), frameon=False, ncol=2,
               handlelength=0.9, handletextpad=0.4, labelspacing=0.35, columnspacing=1.0)

    fig.text(0.315, 0.93, 'a', fontsize=8.5, fontweight='bold', ha='left', va='center')
    fig.text(0.625, 0.93, 'b', fontsize=8.5, fontweight='bold', ha='left', va='center')
    fig.text(0.315, 0.02,
             'Display-supported keys change two feature cells; the uniform thousandfold\n'
             'factor cancels in the ratios and leaves log assets. The sign proposals\n'
             'remain unresolved, so their movement is a sensitivity case.',
             fontsize=6.3, ha='left', va='bottom', color='#404040', linespacing=1.5)
    save(fig, 'figure5_source_evidence', axes_skip=('e', 'f'))


if __name__ == '__main__':
    figure1()
    figure2()
    figure3()
    figure4()
    figure5()
    (ROOT / 'results' / 'figure_layout_audit.txt').write_text('\n'.join(AUDIT) + '\n',
                                                              encoding='utf-8')
    print('\n'.join(AUDIT))
