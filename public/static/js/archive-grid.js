(() => {
    'use strict';

    const grids = Array.from(
        document.querySelectorAll('[data-archive-grid]')
    );

    if (grids.length === 0) {
        return;
    }

    const clamp = (value, min, max) =>
        Math.max(min, Math.min(max, value));

    const layoutGrid = (grid) => {
        const cards = Array.from(grid.children).filter((item) =>
            item.classList.contains('poster-card')
        );

        const count = cards.length;

        if (count === 0) {
            return;
        }

        cards.forEach((card) => {
            card.style.removeProperty('grid-column-start');
        });

        if (window.matchMedia('(max-width: 680px)').matches) {
            grid.classList.remove('is-grid-enhanced');
            grid.style.removeProperty('--archive-columns');
            return;
        }

        const width = grid.clientWidth;
        const computed = window.getComputedStyle(grid);
        const gap = Number.parseFloat(computed.columnGap) || 18;

        if (width <= 0) {
            return;
        }

        const viewport = window.innerWidth;
        const minCardWidth = viewport >= 1800 ? 190 : 175;
        const targetCardWidth = viewport >= 1800 ? 230 : 210;
        const maxCardWidth = viewport >= 1800 ? 280 : 255;

        const minColumns = Math.max(
            1,
            Math.ceil((width + gap) / (maxCardWidth + gap))
        );

        const maxColumns = Math.max(
            minColumns,
            Math.floor((width + gap) / (minCardWidth + gap))
        );

        const idealColumns = clamp(
            Math.round((width + gap) / (targetCardWidth + gap)),
            minColumns,
            maxColumns
        );

        let bestColumns = idealColumns;
        let bestScore = Number.POSITIVE_INFINITY;

        for (
            let columns = minColumns;
            columns <= maxColumns;
            columns += 1
        ) {
            const cardWidth =
                (width - gap * (columns - 1)) / columns;

            const sizePenalty =
                Math.abs(cardWidth - targetCardWidth) /
                targetCardWidth;

            const remainder = count % columns;
            const emptyRatio = remainder === 0
                ? 0
                : (columns - remainder) / columns;

            let rowPenalty = emptyRatio * 0.2;

            if (remainder === 1 && columns > 2) {
                rowPenalty += 0.16;
            }

            const distancePenalty =
                Math.abs(columns - idealColumns) * 0.012;

            const score =
                sizePenalty +
                rowPenalty +
                distancePenalty;

            if (score < bestScore) {
                bestScore = score;
                bestColumns = columns;
            }
        }

        grid.style.setProperty(
            '--archive-columns',
            String(bestColumns)
        );
        grid.classList.add('is-grid-enhanced');

        const remainder = count % bestColumns;

        if (remainder > 0 && remainder < bestColumns) {
            const firstLastRowCard = cards[count - remainder];
            const offset =
                Math.floor((bestColumns - remainder) / 2) + 1;

            firstLastRowCard.style.gridColumnStart = String(offset);
        }
    };

    let frame = 0;

    const scheduleLayout = () => {
        window.cancelAnimationFrame(frame);
        frame = window.requestAnimationFrame(() => {
            grids.forEach(layoutGrid);
        });
    };

    scheduleLayout();

    if ('ResizeObserver' in window) {
        const observer = new ResizeObserver(scheduleLayout);
        grids.forEach((grid) => observer.observe(grid));
    } else {
        window.addEventListener('resize', scheduleLayout, {
            passive: true,
        });
    }

    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(scheduleLayout).catch(() => {});
    }
})();
