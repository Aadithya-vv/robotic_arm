# Affordance Engine Architecture

ENG-013 sits strictly after ENG-012. The Composition Root calls ENG-012’s public contract and adapts immutable Knowledge Records to ENG-013’s structural source. ENG-013 evaluates its owned catalog, builds a checksummed immutable graph/cache, and writes only its derived store. WebAPI/UI are read-only projections.
