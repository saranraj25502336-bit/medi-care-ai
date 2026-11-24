/* ============================================
   MediCare AI - shared UI smoothing helpers
   Loaded on every page with `defer`.
   1. Navbar shadow while scrolling
   2. Reveal animations when a block scrolls into view
   ============================================ */
(function () {
    'use strict';

    var reduceMotion = !!(window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches);

    /* --------------------------------------------
       1. Navbar gets depth once the page scrolls
       -------------------------------------------- */
    var navbars = Array.prototype.slice.call(document.querySelectorAll('.navbar'));

    if (navbars.length) {
        var queued = false;

        var syncNavbars = function () {
            var scrolled = window.scrollY > 12;
            navbars.forEach(function (bar) {
                bar.classList.toggle('scrolled', scrolled);
            });
            queued = false;
        };

        window.addEventListener('scroll', function () {
            if (!queued) {
                queued = true;
                window.requestAnimationFrame(syncNavbars);
            }
        }, { passive: true });

        syncNavbars();
    }

    /* --------------------------------------------
       2. Reveal blocks as they enter the viewport
       Only elements that start below the fold are
       deferred, so nothing already on screen flickers.
       -------------------------------------------- */
    if (reduceMotion || !('IntersectionObserver' in window)) {
        return;
    }

    var REVEAL_SELECTOR = '.animate-fadeInUp, .animate-fadeInDown, ' +
        '.animate-fadeInLeft, .animate-fadeInRight, .animate-scaleIn';

    var belowFold = Array.prototype.slice
        .call(document.querySelectorAll(REVEAL_SELECTOR))
        .filter(function (el) {
            return el.getBoundingClientRect().top >= window.innerHeight * 0.92;
        });

    if (!belowFold.length) {
        return;
    }

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) {
                return;
            }
            var el = entry.target;
            /* Drop the inline overrides so the class animation replays now */
            el.style.animationName = '';
            el.style.opacity = '';
            observer.unobserve(el);
        });
    }, { threshold: 0.08, rootMargin: '0px 0px -6% 0px' });

    belowFold.forEach(function (el) {
        el.style.animationName = 'none';
        el.style.opacity = '0';
        observer.observe(el);
    });
})();
