/* Shared Theme Toggle, Crisp SVG Icons, and Song Label Helpers for Melodle */

(function () {
	const STORAGE_KEY = "melodle-theme";

	const ICONS = {
		sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path></svg>',
		moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path></svg>',
		play: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="6,4 20,12 6,20"></polygon></svg>',
		pause: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4.5" height="16" rx="1"></rect><rect x="13.5" y="4" width="4.5" height="16" rx="1"></rect></svg>',
		stop: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>',
		skip: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 4 15 12 5 20 5 4"></polygon><line x1="19" y1="5" x2="19" y2="19"></line></svg>',
		prev: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>',
		next: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>',
		submit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>',
		speaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg>',
		volumeDown: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="22" y1="9" x2="16" y2="15"></line><line x1="16" y1="9" x2="22" y2="15"></line></svg>',
		check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
		alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
		x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
		plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
		restart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg>',
		star: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>'
	};

	function getActiveTheme() {
		return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
	}

	function syncThemeButton() {
		const btn = document.getElementById("themeToggle");
		if (!btn) return;
		const isDark = getActiveTheme() === "dark";
		btn.innerHTML = (isDark ? ICONS.sun : ICONS.moon) + "<span>" + (isDark ? "Light Mode" : "Dark Mode") + "</span>";
		btn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
	}

	function applyTheme(theme) {
		const clean = theme === "dark" ? "dark" : "light";
		document.documentElement.classList.add("theme-snap");
		document.documentElement.setAttribute("data-theme", clean);
		try {
			localStorage.setItem(STORAGE_KEY, clean);
		} catch (e) {}
		syncThemeButton();
		void document.documentElement.offsetHeight;
		document.documentElement.classList.remove("theme-snap");
	}

	window.toggleTheme = function () {
		applyTheme(getActiveTheme() === "dark" ? "light" : "dark");
	};

	window.MELODLE_ICONS = ICONS;

	function splitSongTitleArtist(fullStr, knownArtist) {
		if (knownArtist && fullStr.endsWith(" - " + knownArtist)) {
			return [fullStr.slice(0, fullStr.length - knownArtist.length - 3), knownArtist];
		}
		const sep = fullStr.lastIndexOf(" - ");
		if (sep === -1) {
			return [fullStr, ""];
		}
		return [fullStr.slice(0, sep), fullStr.slice(sep + 3)];
	}

	// Build two-tone highlighted autocomplete row (Title on left, Artist on right)
	window.buildAutocompleteItem = function (itemValue, query, knownArtist) {
		const row = document.createElement("DIV");
		const parts = splitSongTitleArtist(itemValue, knownArtist);
		const titlePart = parts[0];
		const artistPart = parts[1];

		function appendHighlighted(container, text, q) {
			if (!q) {
				container.appendChild(document.createTextNode(text));
				return;
			}
			const idx = text.toUpperCase().indexOf(q.toUpperCase());
			if (idx === -1) {
				container.appendChild(document.createTextNode(text));
				return;
			}
			container.appendChild(document.createTextNode(text.slice(0, idx)));
			const strong = document.createElement("STRONG");
			strong.textContent = text.slice(idx, idx + q.length);
			container.appendChild(strong);
			container.appendChild(document.createTextNode(text.slice(idx + q.length)));
		}

		const titleSpan = document.createElement("SPAN");
		titleSpan.className = "ac-title";
		appendHighlighted(titleSpan, titlePart, query);
		row.appendChild(titleSpan);

		if (artistPart) {
			const artistSpan = document.createElement("SPAN");
			artistSpan.className = "ac-artist";
			appendHighlighted(artistSpan, artistPart, query);
			row.appendChild(artistSpan);
		}
		return row;
	};

	// Set two-tone Title + Artist inside a solved guess element cleanly
	window.setFormattedSongText = function (el, fullSongStr, knownArtist) {
		if (!el) return;
		el.innerHTML = "";
		el.title = fullSongStr;
		const parts = splitSongTitleArtist(fullSongStr, knownArtist);
		if (!parts[1]) {
			el.textContent = fullSongStr;
			return;
		}
		const tSpan = document.createElement("span");
		tSpan.className = "song-label-title";
		tSpan.textContent = parts[0];
		const aSpan = document.createElement("span");
		aSpan.className = "song-label-artist";
		aSpan.textContent = " — " + parts[1];
		el.appendChild(tSpan);
		el.appendChild(aSpan);
	};

	// Custom Editorial / Studio Vinyl Calendar Popover
	function initMelodleDatePickers() {
		const wraps = document.querySelectorAll(".date-picker-wrap");
		if (!wraps.length) return;

		const MONTHS = [
			"January", "February", "March", "April", "May", "June",
			"July", "August", "September", "October", "November", "December"
		];
		const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

		let popover = document.getElementById("melodle-calendar");
		if (!popover) {
			popover = document.createElement("div");
			popover.id = "melodle-calendar";
			popover.className = "cal-popover";
			popover.setAttribute("role", "dialog");
			popover.setAttribute("aria-label", "Choose a date");
			popover.hidden = true;
			document.body.appendChild(popover);
		}

		let activeWrap = null;
		let activeInput = null;
		let viewYear = 2026;
		let viewMonth = 0;

		function fmtYmd(y, m, d) {
			return String(y) + "-" + String(m + 1).padStart(2, "0") + "-" + String(d).padStart(2, "0");
		}

		function parseYmd(s) {
			if (!s || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
			const p = s.split("-");
			return { y: Number(p[0]), m: Number(p[1]) - 1, d: Number(p[2]) };
		}

		function getTodayStr() {
			const now = new Date();
			return fmtYmd(now.getFullYear(), now.getMonth(), now.getDate());
		}

		function getBounds(inp) {
			const todayStr = getTodayStr();
			const minStr = inp.getAttribute("min") || inp.min || "1958-01-01";
			const maxStr = inp.getAttribute("max") || inp.max || todayStr;
			return {
				minStr: minStr,
				maxStr: maxStr,
				min: parseYmd(minStr) || { y: 1958, m: 0, d: 1 },
				max: parseYmd(maxStr) || parseYmd(todayStr)
			};
		}

		function positionPopover() {
			if (!activeWrap || popover.hidden) return;
			const rect = activeWrap.getBoundingClientRect();
			const popW = popover.offsetWidth || 284;
			const popH = popover.offsetHeight || 310;
			let left = rect.right - popW;
			if (left < 12) left = 12;
			if (left + popW > window.innerWidth - 12) {
				left = Math.max(12, window.innerWidth - popW - 12);
			}
			let top = rect.bottom + 8;
			if (top + popH > window.innerHeight - 12 && rect.top - popH - 8 >= 12) {
				top = rect.top - popH - 8;
			}
			if (top + popH > window.innerHeight - 12) {
				top = Math.max(12, window.innerHeight - popH - 12);
			}
			popover.style.left = Math.round(left) + "px";
			popover.style.top = Math.round(top) + "px";
		}

		function closeCalendar() {
			if (popover.hidden) return;
			popover.hidden = true;
			if (activeWrap) {
				activeWrap.classList.remove("is-open");
				activeWrap.setAttribute("aria-expanded", "false");
			}
			activeWrap = null;
			activeInput = null;
		}

		function clampViewToBounds(bounds) {
			if (viewYear < bounds.min.y) {
				viewYear = bounds.min.y;
				viewMonth = bounds.min.m;
			} else if (viewYear === bounds.min.y && viewMonth < bounds.min.m) {
				viewMonth = bounds.min.m;
			}
			if (viewYear > bounds.max.y) {
				viewYear = bounds.max.y;
				viewMonth = bounds.max.m;
			} else if (viewYear === bounds.max.y && viewMonth > bounds.max.m) {
				viewMonth = bounds.max.m;
			}
		}

		function selectDateStr(ymd) {
			if (!activeInput) return;
			const targetInput = activeInput;
			closeCalendar();
			targetInput.value = ymd;
			targetInput.dispatchEvent(new Event("change", { bubbles: true }));
		}

		function renderCalendar() {
			if (!activeInput) return;
			const bounds = getBounds(activeInput);
			clampViewToBounds(bounds);
			const selectedStr = activeInput.value || "";
			const todayStr = getTodayStr();

			let focusTarget = null;
			const prevFocused = document.activeElement;
			if (prevFocused && popover.contains(prevFocused)) {
				if (prevFocused.classList.contains("cal-month-select")) focusTarget = "month";
				else if (prevFocused.classList.contains("cal-year-select")) focusTarget = "year";
				else if (prevFocused.dataset && prevFocused.dataset.calRole) focusTarget = prevFocused.dataset.calRole;
			}

			popover.innerHTML = "";

			// Header: Prev + Month Select + Year Select + Next
			const header = document.createElement("div");
			header.className = "cal-header";

			const prevBtn = document.createElement("button");
			prevBtn.type = "button";
			prevBtn.className = "cal-nav-btn";
			prevBtn.dataset.calRole = "prev";
			prevBtn.setAttribute("aria-label", "Previous month");
			prevBtn.innerHTML = ICONS.prev;
			prevBtn.disabled = (viewYear < bounds.min.y) || (viewYear === bounds.min.y && viewMonth <= bounds.min.m);
			prevBtn.onclick = function (e) {
				e.stopPropagation();
				viewMonth--;
				if (viewMonth < 0) {
					viewMonth = 11;
					viewYear--;
				}
				renderCalendar();
			};

			const selectsWrap = document.createElement("div");
			selectsWrap.className = "cal-selects";

			const monthSel = document.createElement("select");
			monthSel.className = "cal-select cal-month-select";
			monthSel.setAttribute("aria-label", "Month");
			for (let m = 0; m < 12; m++) {
				const opt = document.createElement("option");
				opt.value = String(m);
				opt.textContent = MONTHS[m];
				if ((viewYear === bounds.min.y && m < bounds.min.m) || (viewYear === bounds.max.y && m > bounds.max.m)) {
					opt.disabled = true;
				}
				if (m === viewMonth) opt.selected = true;
				monthSel.appendChild(opt);
			}
			monthSel.onchange = function () {
				viewMonth = Number(monthSel.value);
				renderCalendar();
			};

			const yearSel = document.createElement("select");
			yearSel.className = "cal-select cal-year-select";
			yearSel.setAttribute("aria-label", "Year");
			for (let y = bounds.max.y; y >= bounds.min.y; y--) {
				const opt = document.createElement("option");
				opt.value = String(y);
				opt.textContent = String(y);
				if (y === viewYear) opt.selected = true;
				yearSel.appendChild(opt);
			}
			yearSel.onchange = function () {
				viewYear = Number(yearSel.value);
				clampViewToBounds(bounds);
				renderCalendar();
			};

			selectsWrap.appendChild(monthSel);
			selectsWrap.appendChild(yearSel);

			const nextBtn = document.createElement("button");
			nextBtn.type = "button";
			nextBtn.className = "cal-nav-btn";
			nextBtn.dataset.calRole = "next";
			nextBtn.setAttribute("aria-label", "Next month");
			nextBtn.innerHTML = ICONS.next;
			nextBtn.disabled = (viewYear > bounds.max.y) || (viewYear === bounds.max.y && viewMonth >= bounds.max.m);
			nextBtn.onclick = function (e) {
				e.stopPropagation();
				viewMonth++;
				if (viewMonth > 11) {
					viewMonth = 0;
					viewYear++;
				}
				renderCalendar();
			};

			header.appendChild(prevBtn);
			header.appendChild(selectsWrap);
			header.appendChild(nextBtn);
			popover.appendChild(header);

			// Weekday labels
			const wkRow = document.createElement("div");
			wkRow.className = "cal-weekdays";
			for (let i = 0; i < 7; i++) {
				const sp = document.createElement("span");
				sp.textContent = WEEKDAYS[i];
				wkRow.appendChild(sp);
			}
			popover.appendChild(wkRow);

			// Days grid
			const grid = document.createElement("div");
			grid.className = "cal-grid";
			const firstDow = new Date(viewYear, viewMonth, 1).getDay();
			const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

			for (let e = 0; e < firstDow; e++) {
				const blank = document.createElement("span");
				blank.className = "cal-empty";
				grid.appendChild(blank);
			}

			for (let d = 1; d <= daysInMonth; d++) {
				const ymd = fmtYmd(viewYear, viewMonth, d);
				const btn = document.createElement("button");
				btn.type = "button";
				btn.className = "cal-day";
				btn.textContent = String(d);
				if (ymd === selectedStr) btn.classList.add("is-selected");
				if (ymd === todayStr) btn.classList.add("is-today");
				if (ymd < bounds.minStr || ymd > bounds.maxStr) {
					btn.disabled = true;
				} else {
					btn.onclick = function (ev) {
						ev.stopPropagation();
						selectDateStr(ymd);
					};
				}
				grid.appendChild(btn);
			}
			popover.appendChild(grid);

			// Today shortcut footer when today is within bounds
			if (todayStr >= bounds.minStr && todayStr <= bounds.maxStr) {
				const footer = document.createElement("div");
				footer.className = "cal-footer";
				const todayBtn = document.createElement("button");
				todayBtn.type = "button";
				todayBtn.className = "cal-today-btn";
				todayBtn.textContent = "Today";
				todayBtn.onclick = function (ev) {
					ev.stopPropagation();
					selectDateStr(todayStr);
				};
				footer.appendChild(todayBtn);
				popover.appendChild(footer);
			}

			positionPopover();

			if (focusTarget === "month") {
				monthSel.focus();
			} else if (focusTarget === "year") {
				yearSel.focus();
			} else if (focusTarget === "prev") {
				(prevBtn.disabled ? nextBtn : prevBtn).focus();
			} else if (focusTarget === "next") {
				(nextBtn.disabled ? prevBtn : nextBtn).focus();
			}
		}

		function openCalendar(wrap, inp) {
			if (wrap.classList.contains("is-disabled")) return;
			if (activeWrap === wrap && !popover.hidden) {
				closeCalendar();
				return;
			}
			if (activeWrap) {
				activeWrap.classList.remove("is-open");
				activeWrap.setAttribute("aria-expanded", "false");
			}
			activeWrap = wrap;
			activeInput = inp;
			wrap.classList.add("is-open");
			wrap.setAttribute("aria-expanded", "true");

			const bounds = getBounds(inp);
			const parsed = parseYmd(inp.value) || bounds.max;
			viewYear = parsed.y;
			viewMonth = parsed.m;
			clampViewToBounds(bounds);

			popover.hidden = false;
			renderCalendar();
		}

		wraps.forEach(function (wrap) {
			const inp = wrap.querySelector(".date-picker");
			if (!inp) return;
			inp.type = "hidden";
			wrap.setAttribute("role", "button");
			wrap.setAttribute("tabindex", "0");
			wrap.setAttribute("aria-haspopup", "dialog");
			wrap.setAttribute("aria-expanded", "false");

			wrap.addEventListener("click", function (e) {
				e.preventDefault();
				openCalendar(wrap, inp);
			});

			wrap.addEventListener("keydown", function (e) {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					openCalendar(wrap, inp);
				}
			});
		});

		document.addEventListener("mousedown", function (e) {
			if (popover.hidden) return;
			if (!popover.contains(e.target) && (!activeWrap || !activeWrap.contains(e.target))) {
				closeCalendar();
			}
		});

		document.addEventListener("keydown", function (e) {
			if (e.key === "Escape" && !popover.hidden) {
				const prevWrap = activeWrap;
				closeCalendar();
				if (prevWrap) prevWrap.focus();
			}
		});

		window.addEventListener("resize", positionPopover);
		window.addEventListener("scroll", positionPopover, true);
	}

	syncThemeButton();
	document.addEventListener("DOMContentLoaded", function () {
		syncThemeButton();
		initMelodleDatePickers();
	});
})();
