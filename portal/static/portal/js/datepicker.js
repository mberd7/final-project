/* Date picker for <input class="date-input">: always day.month.year (25.12.26).
 *
 * The browser's own <input type="date"> shows the date in the order of the
 * browser's language (often mm/dd/yyyy), and a website cannot change that.
 * So these are plain text inputs: you can type "251226" (the dots appear
 * by themselves) or click the field and pick a day in a small calendar.
 *
 * data-min="2026-11-12" -> earlier days are greyed out.
 * In a form with start_date and end_date, the return date can't be before
 * the pick-up date: choosing a later pick-up day clears the return day.
 */
(function () {
    const MONTHS = ["იანვარი", "თებერვალი", "მარტი", "აპრილი", "მაისი", "ივნისი",
        "ივლისი", "აგვისტო", "სექტემბერი", "ოქტომბერი", "ნოემბერი", "დეკემბერი"];
    const WEEKDAYS = ["ორ", "სამ", "ოთხ", "ხუთ", "პარ", "შაბ", "კვი"];

    const pad = (n) => String(n).padStart(2, "0");
    const show = (d) => `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${pad(d.getFullYear() % 100)}`;
    const fromIso = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };

    // "25.12.26" (or the full year "25.12.2026") -> Date, or null if it isn't a real day (31.02 is rejected)
    function read(text) {
        const m = /^(\d{2})\.(\d{2})\.(\d{2}|\d{4})$/.exec(text.trim());
        if (!m) return null;
        const year = m[3].length === 2 ? 2000 + +m[3] : +m[3];
        const d = new Date(year, +m[2] - 1, +m[1]);
        return d.getDate() === +m[1] && d.getMonth() === +m[2] - 1 ? d : null;
    }

    function partner(input, name) {
        return input.form ? input.form.querySelector(`.date-input[name="${name}"]`) : null;
    }

    function minDate(input) {
        let min = input.dataset.min ? fromIso(input.dataset.min) : null;
        if (input.name === "end_date") {                 // return day >= pick-up day
            const start = partner(input, "start_date");
            const s = start && read(start.value);
            if (s && (!min || s > min)) min = s;
        }
        return min;
    }

    let open = null;   // the popup that is currently shown

    function close() {
        if (open) { open.el.remove(); open.input.setAttribute("aria-expanded", "false"); open = null; }
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function openFor(input) {
        if (open && open.input === input) return;
        close();
        const chosen = read(input.value);
        const min = minDate(input);
        const first = chosen || min || new Date();
        const pop = el("div", "datepicker cal");
        pop.setAttribute("role", "dialog");
        pop.setAttribute("aria-label", "აირჩიეთ თარიღი");
        open = { el: pop, input, view: new Date(first.getFullYear(), first.getMonth(), 1) };
        input.setAttribute("aria-expanded", "true");
        input.closest(".field").append(pop);
        render();
    }

    function render() {
        const { el: pop, input, view } = open;
        const chosen = read(input.value);
        const min = minDate(input);
        const today = new Date(); today.setHours(0, 0, 0, 0);
        pop.innerHTML = "";

        const head = el("div", "cal-head");
        const prev = el("button", "cal-nav", "‹");
        const next = el("button", "cal-nav", "›");
        prev.type = next.type = "button";
        prev.setAttribute("aria-label", "წინა თვე");
        next.setAttribute("aria-label", "შემდეგი თვე");
        prev.disabled = !!min && view <= new Date(min.getFullYear(), min.getMonth(), 1);
        prev.onclick = () => { open.view = new Date(view.getFullYear(), view.getMonth() - 1, 1); render(); };
        next.onclick = () => { open.view = new Date(view.getFullYear(), view.getMonth() + 1, 1); render(); };
        head.append(prev, el("span", "cal-title", `${MONTHS[view.getMonth()]} ${view.getFullYear()}`), next);

        const grid = el("div", "cal-grid");
        WEEKDAYS.forEach((w) => grid.append(el("span", "cal-dow", w)));
        for (let i = 0; i < (view.getDay() + 6) % 7; i++) grid.append(el("span"));   // Monday first
        const count = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
        for (let n = 1; n <= count; n++) {
            const d = new Date(view.getFullYear(), view.getMonth(), n);
            const b = el("button", "cal-day", n);
            b.type = "button";
            b.disabled = !!min && d < min;
            b.setAttribute("aria-label", `${n} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`);
            if (d.getTime() === today.getTime()) b.classList.add("is-today");
            if (chosen && d.getTime() === chosen.getTime()) b.classList.add("is-start", "is-end");
            b.onclick = () => pick(input, d);
            grid.append(b);
        }
        pop.append(head, grid);
    }

    function pick(input, d) {
        input.value = show(d);
        close();
        changed(input);
        input.focus();
    }

    // A new pick-up day after the return day makes the return day invalid: clear it
    function changed(input) {
        if (input.name !== "start_date") return;
        const end = partner(input, "end_date");
        const s = read(input.value), e = end && read(end.value);
        if (s && e && e < s) end.value = "";
    }

    document.querySelectorAll(".date-input").forEach((input) => {
        input.setAttribute("aria-haspopup", "dialog");
        input.setAttribute("aria-expanded", "false");
        input.addEventListener("focus", () => openFor(input));
        input.addEventListener("click", () => openFor(input));

        // Typing: keep only digits and add the dots: 251226 -> 25.12.26 (8 digits -> full year)
        input.addEventListener("input", () => {
            const digits = input.value.replace(/\D/g, "").slice(0, 8);
            input.value = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join(".");
            const d = read(input.value);
            if (d && open && open.input === input) { open.view = new Date(d.getFullYear(), d.getMonth(), 1); render(); }
            if (d) changed(input);
        });
        input.addEventListener("keydown", (e) => { if (e.key === "Escape" || e.key === "Tab") close(); });
    });

    document.addEventListener("click", (e) => {
        // composedPath() is taken when the click starts, so it still contains the popup
        // even if the click redrew the calendar (‹ › buttons) and removed the clicked button
        if (open && !e.composedPath().includes(open.el) && e.target !== open.input) close();
    });
})();
