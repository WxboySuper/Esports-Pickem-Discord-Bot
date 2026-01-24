## 2025-05-12 - Stats Calculation Performance
**Learning:** The application was fetching all `Pick` objects for a user (potentially thousands) just to count how many were "correct". This is a classic N+1-like issue where data transfer and object hydration overhead dominate.
**Action:** Always use SQL aggregation (`count()`, `sum()`) for statistics instead of fetching objects to application memory. In this case, it yielded a ~10x speedup for 1000 records.
