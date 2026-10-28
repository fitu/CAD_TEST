"""Explanatory schematic, not a simulated belt shape or load analysis."""
from pathlib import Path
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, PathPatch
from matplotlib.path import Path as MplPath


def main():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8))
    fig.suptitle('How the apron rolls the paper — schematic side view', fontsize=18, weight='bold')
    for ax, spacing, title in zip(axes, (36, 24), ('1. Pull follower outward to load', '2. Close follower, turn wheel and feed paper')):
        front, rear = -12, -12 + spacing
        ax.add_patch(Circle((front, 0), 8, facecolor='#e7b665', edgecolor='#725228', lw=2))
        ax.add_patch(Circle((rear, 0), 8, facecolor='#dddfe3', edgecolor='#606876', lw=2))
        for y in (front, rear):
            ax.add_patch(Circle((y, 0), 1.4, color='#606876'))
        # Deliberately schematic pocket and return span: not a dimensioned apron profile.
        mid = (front + rear) / 2
        # Tangent lines link the drums to an illustrative rounded pocket.
        pocket_r, pocket_z = 4.4, -4.2
        theta = math.atan2(pocket_z, spacing / 2) + math.acos((8 + pocket_r) / math.hypot(spacing / 2, pocket_z))
        left_circle = [(front + 8 * math.cos(t), 8 * math.sin(t))
                       for t in np.linspace(1.5 * math.pi, theta, 90)]
        left_pocket = (mid - pocket_r * math.cos(theta), pocket_z - pocket_r * math.sin(theta))
        pa = math.atan2(left_pocket[1] - pocket_z, left_pocket[0] - mid) % (2 * math.pi)
        pocket = [(mid + pocket_r * math.cos(t), pocket_z + pocket_r * math.sin(t))
                  for t in np.linspace(pa, 3 * math.pi - pa, 60)]
        right_circle = [(rear + 8 * math.cos(t), 8 * math.sin(t))
                        for t in np.linspace(math.pi - theta, -math.pi / 2, 90)]
        vertices = left_circle + pocket + right_circle
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * (len(vertices) - 1)
        vertices += [(mid + 5, -17), (mid - 5, -17), (front, -8)]
        codes += [MplPath.CURVE4] * 3
        ax.add_patch(PathPatch(MplPath(vertices, codes), facecolor='none', edgecolor='#237bb0', lw=3))
        ax.text(front, -22, 'DRIVE\nD-shaft + wheel', ha='center', va='top', fontsize=10)
        ax.text(rear + 5, 14, 'FOLLOWER\nslides in frame slots', ha='center', fontsize=10)
        ax.annotate('flexible apron', xy=(mid, -14), xytext=(mid + 9, -30),
                    arrowprops={'arrowstyle': '->', 'color': '#237bb0'}, color='#237bb0', ha='center', fontsize=10)
        if spacing == 36:
            ax.text(mid, -4, 'filter +\nherbal material', ha='center', fontsize=10)
            ax.annotate('', xy=(rear + 9, 0), xytext=(rear + 1, 0), arrowprops={'arrowstyle': '->', 'lw': 2})
            ax.text(mid, 22, 'Hold follower open; arrange contents across the roller width.', ha='center', fontsize=10)
        else:
            ax.add_patch(Circle((mid, -4.2), 3.6, facecolor='#71975b', edgecolor='#315729', lw=1.5))
            ax.annotate('forming roll', xy=(mid, -4), xytext=(mid + 2, 4), arrowprops={'arrowstyle': '->'}, fontsize=10)
            ax.annotate('paper: ungummed long edge first', xy=(front + 8, -0.5), xytext=(front - 10, 22),
                        arrowprops={'arrowstyle': '->', 'color': '#7d4cb5'}, color='#7d4cb5', fontsize=10)
            ax.annotate('', xy=(front + 7, 7), xytext=(front + 3, 11), arrowprops={'arrowstyle': '->', 'lw': 2, 'color': '#237bb0'})
        ax.set_title(title, fontsize=12, pad=16)
        ax.set_xlim(-38, 49)
        ax.set_ylim(-39, 31)
        ax.set_aspect('equal')
        ax.axis('off')
    fig.text(0.5, 0.04, 'The real belt deforms around the contents. CAD shows a reference envelope only. Paper feeding and apron length require physical trials.',
             ha='center', fontsize=10)
    fig.subplots_adjust(top=0.81, bottom=0.1, wspace=0.04)
    dest = Path('docs/how_it_works.png')
    dest.parent.mkdir(exist_ok=True)
    fig.savefig(dest, dpi=160, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
