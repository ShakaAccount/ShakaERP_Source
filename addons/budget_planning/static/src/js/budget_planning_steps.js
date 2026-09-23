/** @odoo-module **/

(() => {
    const pages = ["strategies", "targets", "kpis", "initiatives", "projects", "activities", "budget"];

    const openPage = (root, pageName) => {
        const notebook = root.querySelector('.bp-main .o_notebook');
        const tab = notebook?.querySelector(`.o_notebook_headers [data-name="${pageName}"]`)
            || notebook?.querySelector(`.o_notebook_headers a[name="${pageName}"]`);
        if (tab) {
            tab.click();
            syncSteps(root, pageName);
            syncStageActions(root, pageName);
        }
    };

    const syncSteps = (root, pageName) => {
        root.querySelectorAll('.bp-step[data-bp-page]').forEach((step) => {
            step.classList.toggle('active', step.dataset.bpPage === pageName);
        });
    };

    const getActivePage = (root) => root.querySelector('.bp-step.active')?.dataset.bpPage || pages[0];

    const getUnlockedStep = (root) => {
        const field = root.querySelector('[name="unlocked_step"]');
        const rawValue = field?.querySelector('input')?.value || field?.textContent || '1';
        // Odoo may localize integer fields with Persian/Arabic digits. Use
        // Unicode escapes so this conversion stays correct regardless of the
        // file encoding used by the asset build.
        const normalized = String(rawValue)
            .replace(/[\u06F0-\u06F9]/g, (digit) => String(digit.charCodeAt(0) - 0x06F0))
            .replace(/[\u0660-\u0669]/g, (digit) => String(digit.charCodeAt(0) - 0x0660));
        return Math.max(1, Number.parseInt(normalized, 10) || 1);
    };

    const waitForUnlock = (root, nextStep) => {
        let attempts = 0;
        const waitForResult = () => {
            const currentRoot = [...document.querySelectorAll('.o_form_view')]
                .find((form) => form.querySelector('.bp-top'));
            const hasValidationError = currentRoot?.querySelector('.o_field_invalid, .o_invalid_cell');
            if (hasValidationError || !currentRoot) return;
            if (getUnlockedStep(currentRoot) >= nextStep) {
                openPage(currentRoot, pages[nextStep - 1]);
                return;
            }
            if (attempts++ < 20) {
                window.setTimeout(waitForResult, 180);
                return;
            }
        };
        window.setTimeout(waitForResult, 180);
    };

    const syncStageActions = (root, pageName = getActivePage(root)) => {
        const actions = root.querySelector('.bp-actions');
        if (!actions) return;

        const pageIndex = pages.indexOf(pageName);
        const unlockedStep = getUnlockedStep(root);
        root.querySelectorAll('.bp-step[data-bp-page]').forEach((step, index) => {
            const locked = index + 1 > unlockedStep;
            step.classList.toggle('bp-step--locked', locked);
            step.setAttribute('aria-disabled', String(locked));
        });

        const finalButton = actions.querySelector('.bp-final-submit');
        if (finalButton) {
            finalButton.style.display = pageIndex === pages.length - 1 ? '' : 'none';
        }

        actions.querySelectorAll('.bp-next-step').forEach((button) => {
            const buttonStep = Number.parseInt(button.dataset.bpStep, 10);
            button.style.display = buttonStep === pageIndex + 1 ? '' : 'none';
        });
    };

    const syncControlPanelState = (root) => {
        const controlPanel = document.querySelector('.o_control_panel');
        const target = controlPanel?.querySelector('.o_control_panel_main_buttons')
            || controlPanel?.querySelector('.o_control_panel_breadcrumbs');
        const statusbar = root.querySelector('.o_form_statusbar .o_field_statusbar');
        if (!target || !statusbar) return;

        const active = statusbar.querySelector('[aria-current="step"]')
            || statusbar.querySelector('.o_arrow_button_current')
            || statusbar.querySelector('button:not(.d-none)');
        const label = active?.textContent?.trim();
        if (!label) return;

        let chip = target.querySelector('.bp-control-state');
        if (!chip) {
            chip = document.createElement('span');
            chip.className = 'bp-control-state';
            target.append(chip);
        }
        if (chip.textContent !== label) {
            chip.textContent = label;
        }
        if (!root.classList.contains('bp-control-state-ready')) {
            root.classList.add('bp-control-state-ready');
        }
    };

    const wirePlan = (root) => {
        if (root.dataset.bpStepsReady === '1') return;
        const notebook = root.querySelector('.bp-main .o_notebook');
        if (!notebook) return;
        root.dataset.bpStepsReady = '1';

        root.querySelectorAll('.bp-step[data-bp-page]').forEach((step) => {
            step.addEventListener('click', () => {
                if (step.classList.contains('bp-step--locked')) return;
                const pageName = step.dataset.bpPage;
                openPage(root, pageName);
            });
        });

        root.querySelectorAll('.bp-next-step').forEach((button) => {
            button.addEventListener('click', () => {
                const currentStep = Number.parseInt(button.dataset.bpStep, 10);
                if (currentStep >= 1 && currentStep < pages.length) {
                    waitForUnlock(root, currentStep + 1);
                }
            });
        });

        notebook.addEventListener('click', (event) => {
            const tab = event.target.closest('.o_notebook_headers [data-name], .o_notebook_headers a[name]');
            if (tab) {
                const pageName = tab.dataset.name || tab.getAttribute('name');
                syncSteps(root, pageName);
                syncStageActions(root, pageName);
            }
        });
    };

    // Avoid :has() here: an unsupported selector can stop the whole backend
    // asset bundle and leave the Odoo home screen blank.
    const start = () => {
        if (!document.body) return;

        const scan = () => document.querySelectorAll('.o_form_view').forEach((form) => {
            if (form.querySelector('.bp-top')) {
                wirePlan(form);
                syncControlPanelState(form);
                syncStageActions(form);
            }
        });

        scan();
        new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
        start();
    }
})();
