### Master-Order-Plan-Uncertainty-with-python
Find the for an Assemble To order strategy the optimal ordering plan of your supplies to meet your customers demand and reduce holding costs



Imagine you manage a complex Assemble-To-Order (ATO) manufacturing line. You
have a perfect demand forecast, and 99% of your components are ready in the
warehouse. But because of a single delayed shipment from a supplier your entire assembly line grinds to a halt.

In a traditional Material Requirements Planning (MRP) system, planners use
"average" lead times to calculate when to order parts. But in the real world,
averages are dangerous. If a supplier promises a 2-week delivery, but
occasionally takes 4 weeks, placing orders based on the average guarantees
stockouts. Because a perfect Just-In-Time system assumes zero variability, the
entirety of a company's holding cost in a real-world ATO environment is
effectively a massive "Risk Buffer."

In this project, we used python and stochastic linear programming in order to determine an ordering plan guaranteeing service without bumping up stocks.
Furthermore we will undercover how we could reduce costs even more by changing one parameter.


To build a realistic model of a global Assemble-to-Order network, the system is fed with four primary data categories.
1. Market Demand Requirements


[1. Market Demand Forecast by End-Item — Image by Author]

Components: Weekly sales forecast per finished end-item.
Assumption: Demand is deterministic over a 15-week planning horizon, allowing the model to focus purely on supply-side uncertainty.
For instance: Finished Item 'F' sees a massive demand spike in week 6, requiring the model to pre-position components 2–4 weeks in advance.

2. Component Holding Costs (Working Capital)

[2. Component Holding Costs — Image by Author]

Components: Cost of tied-up capital, insurance, and risk of obsolescence.
Assumption: High-value components (e.g., CPUs) carry a high weekly "penalty," while low-value parts (e.g., fasteners) are cheap to store.
For instance: Storing Component 16 costs $10.00/unit/week, making it a primary candidate for Just-In-Time (JIT) ordering to protect cash flow.
3. Bill of Materials (BOM) & Product Structure
[3. Bill of Materials (BOM) Mapping — Image by Author]
Components: Mapping of finished goods to their sub-assembly components.
Assumption: An end-item is only "shippable" if 100% of its required components are available; otherwise, the entire order is canceled.
For instance: Assembling 1 unit of Item 'I' requires a "kit" of 3 units of Component 1 and 4 units of Component 3. If either part is missing, the build fails.
4. Stochastic Lead Times (Supplier Reliability)

[4. Lead Time Probability Distributions Extract for 5 Components  — Image by Author]
Components: Probability distributions of delivery times per supplier.
Assumption: Instead of a fixed 2-week arrival, each supplier has a unique probability of being early, on time, or dangerously late.
For instance: Component 1 has a "long-tail" risk. While it usually arrives in 1 week, there is a 15% probability of a 5-week delay, creating the potential for a total system stock-out.
1. The Solution

Here are the results comparing service level performance of the two planning method.



We can see the Stochastic method (where we integrate uncertainty) far outperform the deterministic method (classic ERP scheduling).

3. From Math to Strategy: ROI on Supplier Collaboration

Ok so now what ? Stochastic is a better solution but still an expensive one.
In an ideal world of certainty the holding cost would be minimal because we would order so components arrive just in time.

But what if we can collaborate with suppliers and
improve their reliability ? Which supplier yields the highest ROI?

To answer this, we wrote a sensitivity analysis orchestrator that loops through
every single component, artificially reduces its lead-time variability by 50%,
re-optimizes the system, and tests it out-of-sample to calculate the exact
financial savings.



We can see that we can work with the supplier of C3 to improve its precision. We could promise a $20,000 of bonus that as it’s a 10 week plan would make us gain $47,600 a year!
However, the other parts of the results are surprising! Why improving lead time precision up our costs ? Well because in this simulation as we reduced the variability we also reduced the chances of having shorter lead times.
