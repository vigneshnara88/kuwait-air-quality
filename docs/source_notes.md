# Workflow provenance

The source modules organise methods present in the project's analytical notebooks:

| Project source | Workflow carried into the package |
| --- | --- |
| `proj_kuwait_imputation/code.ipynb` | Long-to-wide pollutant preparation; station-level and station/time missingness. |
| `Time_Series_Analysis.ipynb` | Log PM2.5; wind-direction sine/cosine terms; pollutant interactions; OLS with HC3 covariance; quantile regression. |
| `Kuwait_IDW_.ipynb` | Same-time spatial IDW; power and neighbour-count controls; artificial outages; coverage and tail-error summaries. |

These modules provide a reusable interface with explicit schemas. Station/time lags, outage duration, input validation, and reporting are stated directly in code rather than depending on notebook execution order. In particular, lag matching is within station at exact elapsed hours; artificial outages require consecutive clock-hour observations. No fixed fitted coefficients or historical performance numbers are embedded in the implementation.

Dr Ghita Berrada is principal investigator and Dr Huda Alrashidi is co-principal investigator. Vignesh's contribution is data preparation, missingness analysis, and analytical implementation. Oskar's working material documents spatial modelling and artificial-outage experiments; those contributions are credited in the README rather than presented as Vignesh's sole research. File presence alone is not a claim of exclusive authorship of every source notebook.

The original notebooks, embedded figures, outputs, provisional coordinate dictionaries, monitoring datasets, and collaborators' internal working documents are not redistributed here.
