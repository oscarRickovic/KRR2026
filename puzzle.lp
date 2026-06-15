#const num_copies = 1.

tetracubeType("I").
tetracubeType("T").
tetracubeType("L").
tetracubeType("Pyramid").
tetracubeType("O").
tetracubeType("N").
tetracubeType("Z").
tetracubeType("Z_mirror").

validOrientation("I",        1..3).
validOrientation("T",        1..12).
validOrientation("L",        1..24).
validOrientation("Pyramid",  1..8).
validOrientation("O",        1..3).
validOrientation("N",        1..12).
validOrientation("Z",        1..12).
validOrientation("Z_mirror", 1..12).

typeIndex(1,"I").       typeIndex(2,"T").      typeIndex(3,"L").
typeIndex(4,"Pyramid"). typeIndex(5,"O").      typeIndex(6,"N").
typeIndex(7,"Z").       typeIndex(8,"Z_mirror").

tetracubeID(1..8*num_copies).

assignType(P, Type) :- tetracubeID(P),
                        TI = ((P-1) \ 8) + 1,
                        typeIndex(TI, Type).

1 { position(P,R,X,Y,Z) : cell(X,Y,Z), validOrientation(Type,R) } 1 :-
    tetracubeID(P), assignType(P,Type).

occupied(P, X+DX, Y+DY, Z+DZ) :-
    position(P,R,X,Y,Z), assignType(P,Type),
    cube(Type,R,DX,DY,DZ).

:- position(P,R,X,Y,Z), assignType(P,Type),
   cube(Type,R,DX,DY,DZ),
   not cell(X+DX, Y+DY, Z+DZ).

:- occupied(P1,X,Y,Z), occupied(P2,X,Y,Z), P1 != P2.

cellOccupied(X,Y,Z) :- occupied(P,X,Y,Z), tetracubeID(P).
:- cell(X,Y,Z), not cellOccupied(X,Y,Z).

#const num_hints = 5.
#const seed      = 42.

{ hint(P) : tetracubeID(P) } num_hints.
:- num_hints != #count { P : hint(P) }.

#heuristic hint(P) : tetracubeID(P). [seed@3, false]

#show numCopies(num_copies).

#show assignType/2.

#show fullPosition(P,R,X,Y,Z) : position(P,R,X,Y,Z).

#show hintPosition(P,R,X,Y,Z) : position(P,R,X,Y,Z), hint(P).

#show hint/1.
