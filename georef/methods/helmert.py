import math


def solve_linear_system(matrix, values):
    n = len(values)
    augmented = [row[:] + [values[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-12:
            raise ValueError("Transformation Helmert impossible : systeme singulier")

        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        pivot_value = augmented[col][col]
        augmented[col] = [value / pivot_value for value in augmented[col]]

        for row in range(n):
            if row == col:
                continue

            factor = augmented[row][col]
            augmented[row] = [
                augmented[row][i] - factor * augmented[col][i]
                for i in range(n + 1)
            ]

    return [augmented[row][n] for row in range(n)]


def build_normal_equations(gcps, orientation):
    normal = [[0.0 for _ in range(4)] for _ in range(4)]
    rhs = [0.0 for _ in range(4)]

    for gcp in gcps:
        pixel, line = gcp["pixel"]
        x, y = gcp["geo"]

        if orientation == "direct":
            rows = [
                [pixel, -line, 1.0, 0.0],
                [line, pixel, 0.0, 1.0],
            ]
        elif orientation == "indirect":
            rows = [
                [pixel, line, 1.0, 0.0],
                [-line, pixel, 0.0, 1.0],
            ]
        else:
            raise ValueError(f"Orientation Helmert inconnue : {orientation}")

        values = [x, y]

        for row, value in zip(rows, values):
            for i in range(4):
                rhs[i] += row[i] * value
                for j in range(4):
                    normal[i][j] += row[i] * row[j]

    return normal, rhs


def predict_point(pixel, line, a, b, tx, ty, orientation):
    if orientation == "direct":
        return (
            a * pixel - b * line + tx,
            b * pixel + a * line + ty,
        )

    return (
        a * pixel + b * line + tx,
        b * pixel - a * line + ty,
    )


def build_geotransform(a, b, tx, ty, orientation):
    if orientation == "direct":
        return (tx, a, -b, ty, b, a)

    return (tx, a, b, ty, b, -a)


def estimate_oriented_transform(gcps, orientation):
    """
    Estime une transformation Helmert 2D :
    directe :
      X = a * pixel - b * line + tx
      Y = b * pixel + a * line + ty
    indirecte :
      X = a * pixel + b * line + tx
      Y = b * pixel - a * line + ty
    """
    normal, rhs = build_normal_equations(gcps, orientation)
    a, b, tx, ty = solve_linear_system(normal, rhs)

    residuals = []
    for gcp in gcps:
        pixel, line = gcp["pixel"]
        x, y = gcp["geo"]
        predicted_x, predicted_y = predict_point(
            pixel,
            line,
            a,
            b,
            tx,
            ty,
            orientation,
        )
        dx = predicted_x - x
        dy = predicted_y - y
        residuals.append({
            "pixel": (pixel, line),
            "geo": (x, y),
            "dx": dx,
            "dy": dy,
            "error": math.hypot(dx, dy),
        })

    rms = math.sqrt(
        sum(residual["error"] ** 2 for residual in residuals) / len(residuals)
    )

    return {
        "method": "helmert",
        "orientation": orientation,
        "a": a,
        "b": b,
        "tx": tx,
        "ty": ty,
        "scale": math.hypot(a, b),
        "rotation_deg": math.degrees(math.atan2(b, a)),
        "geotransform": build_geotransform(a, b, tx, ty, orientation),
        "rms": rms,
        "max_error": max(residual["error"] for residual in residuals),
        "residuals": residuals,
    }


def estimate_transform(gcps):
    if len(gcps) < 2:
        raise ValueError("Au moins 2 GCP sont necessaires pour une Helmert 2D")

    candidates = [
        estimate_oriented_transform(gcps, "direct"),
        estimate_oriented_transform(gcps, "indirect"),
    ]

    return min(candidates, key=lambda transform: transform["rms"])
