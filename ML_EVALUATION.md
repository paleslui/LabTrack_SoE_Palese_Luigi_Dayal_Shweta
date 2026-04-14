# ML Integration Evaluation — LabTrack (Stage 8)

## Decision: **No ML component included**

## Evaluation

The following potential ML applications were considered and rejected:

| Candidate application | Why evaluated | Why rejected |
|---|---|---|
| Sample processing time prediction | Could help schedule lab resources | No historical time data collected; dataset too small at deployment for meaningful training |
| Anomaly detection on status sequences | Could flag unusual lifecycle paths | A 5-state machine has only ~10 valid transitions; rule-based validation (already implemented) is 100% accurate and interpretable |
| Sample type classification from metadata | Could auto-suggest types | Sample types are entered manually by researchers who already know the type; automation adds no value |
| Expiry / degradation risk scoring | Could prioritise samples nearing expiry | No degradation timeline data collected; this would require a domain-expert knowledge base, not ML |
| User behaviour analytics | Could detect access anomalies | Far outside the scope of a lab sample tracker; introduces privacy concerns (NFR) |

## Justification

1. **No prediction task exists in the core domain.** LabTrack is a LIMS (Laboratory Information Management System). Its primary purpose is structured data entry, lifecycle tracking, and audit logging — all deterministic operations that are fully handled by business rules and relational constraints.

2. **Insufficient data for training.** A newly deployed LabTrack instance starts with zero samples. ML models require hundreds to thousands of labelled examples to generalise. The system cannot accumulate enough data within the course timeline.

3. **Rule-based validation already solves the problem.** The lifecycle state machine (`ALLOWED_TRANSITIONS` in `models/sample.py`) rejects invalid transitions with 100% accuracy and full interpretability. An ML classifier would be strictly worse: lower accuracy, a black box, and requiring retraining as rules change.

4. **Complexity cost outweighs benefit.** The course rubric rewards *justification*, not ML for its own sake. Adding a half-baked model (e.g., a random forest on 5 features) would introduce a new dependency (scikit-learn), training infrastructure, and model versioning overhead — all for a system whose value comes from reliability, not prediction.

5. **Team feasibility.** The team has mixed programming backgrounds (constraint noted in Stage 1). Implementing, testing, and maintaining an ML component would redirect effort away from the core deliverables that directly serve the lab users.

## Conclusion

ML integration is **not applicable** to LabTrack at this stage. This decision may be revisited if the system accumulates several years of operational data, at which point time-series forecasting for sample lifecycle durations or anomaly detection on access patterns could become feasible.
