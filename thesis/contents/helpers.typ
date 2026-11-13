// Drafting helpers. Set show-todos to false before submission; then search for "todo(" to be sure
// nothing is left.
#let show-todos = true

#let todo(body) = if show-todos {
    block(
        fill: rgb("#fff4cc"),
        stroke: (left: 2pt + rgb("#d4a017")),
        inset: (x: 8pt, y: 6pt),
        width: 100%,
        text(size: 0.85em)[*TODO:* #body],
    )
}

#let todo-inline(body) = if show-todos {
    highlight(fill: rgb("#fff4cc"))[*TODO:* #body]
}
