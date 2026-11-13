/* Booking calendar.
 *
 * Shows one month at a time. Past days and days that are already booked
 * (sent by Django as JSON in #booked-data) cannot be chosen.
 * Click the pick-up day, then the return day. The chosen dates are written
 * into the form's start_date / end_date inputs; Django checks them again.
 */
(function () {
    const root = document.getElementById("calendar");
    if (!root) return;

    const MONTHS = ["იანვარი", "თებერვალი", "მარტი", "აპრილი", "მაისი", "ივნისი",
        "ივლისი", "აგვისტო", "სექტემბერი", "ოქტომბერი", "ნოემბერი", "დეკემბერი"];
    const SHORT = ["იან", "თებ", "მარ", "აპრ", "მაი", "ივნ", "ივლ", "აგვ", "სექ", "ოქტ", "ნოე", "დეკ"];
    const WEEKDAYS = ["ორ", "სამ", "ოთხ", "ხუთ", "პარ", "შაბ", "კვი"];

    const pad = (n) => String(n).padStart(2, "0");
    const parse = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
    const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
    const daysBetween = (a, b) => Math.round((b - a) / 86400000) + 1;   // both days included
    const nice = (d) => `${d.getDate()} ${SHORT[d.getMonth()]}`;
    const monthStart = (d) => new Date(d.getFullYear(), d.getMonth(), 1);

    const price = Number(root.dataset.price);
    const maxDays = Number(root.dataset.maxDays);
    const today = parse(root.dataset.today);
    const lastDay = addDays(today, 365);
    const booked = JSON.parse(document.getElementById("booked-data").textContent)
        .map((r) => [parse(r.start), parse(r.end)]);

    const startInput = document.getElementById("id_start_date");
    const endInput = document.getElementById("id_end_date");
    const msg = document.getElementById("cal-msg");
    const button = document.getElementById("book-btn");
    const out = {
        dates: document.getElementById("sum-dates"),
        calc: document.getElementById("sum-calc"),
        sub: document.getElementById("sum-sub"),
        total: document.getElementById("sum-total"),
    };

    const isBooked = (d) => booked.some(([s, e]) => d >= s && d <= e);
    const isFree = (a, b) => !booked.some(([s, e]) => s <= b && e >= a);
    const isDisabled = (d) => d < today || d > lastDay || isBooked(d);

    let start = null, end = null, hover = null;
    let view = monthStart(today);

    // Dates chosen on the search page (or typed before JS loaded) are pre-selected
    if (startInput.value && endInput.value) {
        const s = parse(startInput.value), e = parse(endInput.value);
        if (s >= today && e >= s && daysBetween(s, e) <= maxDays && isFree(s, e)) {
            start = s; end = e;
            view = monthStart(s);
        } else {
            say("არჩეულ თარიღებში მანქანა დაკავებულია — აირჩიეთ სხვა დღეები.", "error");
        }
    }

    // The calendar replaces the plain date inputs
    document.getElementById("date-fallback").hidden = true;
    root.hidden = false;

    function say(text, kind) {
        msg.textContent = text;
        msg.dataset.kind = kind || "hint";
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function render() {
        root.innerHTML = "";

        const head = el("div", "cal-head");
        const prev = navButton("‹", "წინა თვე", -1);
        prev.disabled = view <= monthStart(today);
        const next = navButton("›", "შემდეგი თვე", 1);
        next.disabled = view >= monthStart(lastDay);
        head.append(prev, el("span", "cal-title", `${MONTHS[view.getMonth()]} ${view.getFullYear()}`), next);

        const grid = el("div", "cal-grid");
        WEEKDAYS.forEach((w) => grid.append(el("span", "cal-dow", w)));
        const offset = (view.getDay() + 6) % 7;       // weeks start on Monday
        for (let i = 0; i < offset; i++) grid.append(el("span"));

        const count = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
        for (let n = 1; n <= count; n++) {
            const d = new Date(view.getFullYear(), view.getMonth(), n);
            const b = el("button", "cal-day", n);
            b.type = "button";
            b.dataset.date = iso(d);
            b.disabled = isDisabled(d);
            b.setAttribute("aria-label", `${n} ${MONTHS[d.getMonth()]}${isBooked(d) ? " — დაკავებულია" : ""}`);
            if (d.getTime() === today.getTime()) b.classList.add("is-today");
            if (isBooked(d)) b.classList.add("is-booked");
            b.addEventListener("click", () => choose(d));
            b.addEventListener("mouseenter", () => { hover = d; paint(); });
            grid.append(b);
        }
        grid.addEventListener("mouseleave", () => { hover = null; paint(); });

        const legend = el("div", "cal-legend");
        legend.innerHTML =
            '<span><i class="lg-sel"></i>არჩეული</span>' +
            '<span><i class="lg-range"></i>პერიოდი</span>' +
            '<span><i class="lg-booked"></i>დაკავებული</span>';

        root.append(head, grid, legend);
        paint();
    }

    function navButton(text, label, step) {
        const b = el("button", "cal-nav", text);
        b.type = "button";
        b.setAttribute("aria-label", label);
        b.addEventListener("click", () => {
            view = new Date(view.getFullYear(), view.getMonth() + step, 1);
            render();
        });
        return b;
    }

    // Colours only: start, end and the days in between (or a preview while hovering)
    function paint() {
        let to = end;
        if (start && !end && hover && hover >= start && isFree(start, hover)) to = hover;
        root.querySelectorAll(".cal-day").forEach((b) => {
            const d = parse(b.dataset.date);
            const t = d.getTime();
            const isStart = !!start && t === start.getTime();
            const isEnd = !!to && t === to.getTime();
            b.classList.toggle("is-start", isStart);
            b.classList.toggle("is-end", isEnd);
            b.classList.toggle("is-range", !!start && !!to && d > start && d < to);
            b.setAttribute("aria-pressed", String(isStart || isEnd || (!!start && !!to && d > start && d < to)));
        });
    }

    function choose(d) {
        say("");
        if (!start || end || d < start) {
            start = d; end = null;
        } else if (!isFree(start, d)) {
            say("ამ პერიოდში მანქანა დაკავებულია — აირჩიეთ სხვა დღეები.", "error");
            start = d; end = null;
        } else if (daysBetween(start, d) > maxDays) {
            say(`ერთი ჯავშანი მაქსიმუმ ${maxDays} დღეა.`, "error");
        } else {
            end = d;
        }
        update();
        paint();
    }

    function update() {
        startInput.value = start ? iso(start) : "";
        endInput.value = end ? iso(end) : "";
        button.disabled = !(start && end);

        if (start && end) {
            const n = daysBetween(start, end);
            out.dates.textContent = `${nice(start)} → ${nice(end)}`;
            out.calc.textContent = `${price} ₾ × ${n} დღე`;
            out.sub.textContent = out.total.textContent = `${price * n} ₾`;
            if (msg.dataset.kind !== "error") say(`${n} დღე არჩეულია.`);
        } else {
            out.dates.textContent = start ? `${nice(start)} → ?` : "—";
            out.calc.textContent = `${price} ₾ × 0 დღე`;
            out.sub.textContent = out.total.textContent = "0 ₾";
            if (msg.dataset.kind !== "error") {
                say(start ? "ახლა აირჩიეთ დაბრუნების დღე." : "აირჩიეთ აყვანის დღე.");
            }
        }
    }

    render();
    update();
})();
