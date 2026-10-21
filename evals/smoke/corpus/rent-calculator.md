# Rent calculator

The `late_fee` function computes the penalty for a late payment.

```python
def late_fee(rent: float, days_late: int) -> float:
    if days_late <= 10:
        return 0.0
    return round(rent * 0.05, 2)
```

Penalties are rounded to the nearest cent.
