# Local Customer Validation Protocol

Before commercial accuracy claims are made for a customer estate environment, create a customer-field validation set that is **not used for retraining** during the same acceptance cycle.

Recommended process:

1. Collect representative mobile photographs across estates, divisions, seasons, devices, lighting conditions, leaf ages and backgrounds.
2. Obtain the reference diagnosis from the customer's authorised agronomy / plant-pathology process.
3. Keep ambiguous or mixed-disease images explicitly labelled as such rather than forcing a class.
4. Freeze the model file and SHA-256 before evaluation.
5. Report overall accuracy, balanced accuracy, Macro F1, per-class precision/recall/F1 and confusion matrix.
6. Separately report images rejected as unusable or outside the six supported classes.
7. Review high-confidence errors, not only low-confidence cases.
8. Define the operating policy for AI screening vs. human confirmation.
9. Sign the validation report with dataset date range, model hash and responsible reviewers.
10. Revalidate after material model, camera, preprocessing or class-definition changes.

The current public-dataset benchmark should remain visible as a development benchmark, not a customer-site performance guarantee.
