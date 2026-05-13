# Master-Order-Plan-Uncertainty-with-python

> **Find the optimal ordering plan for an Assemble-To-Order (ATO) strategy to meet your customers' demand and reduce holding costs.**

Imagine you manage a complex Assemble-To-Order (ATO) manufacturing line. You have a perfect demand forecast, and 99% of your components are ready in the warehouse. But because of a single delayed shipment from a supplier, your entire assembly line grinds to a halt.

In a traditional Material Requirements Planning (MRP) system, planners use "average" lead times to calculate when to order parts. But in the real world, averages are dangerous. If a supplier promises a 2-week delivery but occasionally takes 4 weeks, placing orders based on the average guarantees stockouts. Because a perfect Just-In-Time (JIT) system assumes zero variability, the entirety of a company's holding cost in a real-world ATO environment is effectively a massive **"Risk Buffer."**

In this project, we use Python and **stochastic linear programming** to determine an ordering plan that guarantees service without bumping up stocks. Furthermore, we will uncover how we can reduce costs even more by optimizing a single parameter.

---

## 📊 Data Inputs

To build a realistic model of a global Assemble-to-Order network, the system is fed with four primary data categories:

### 1. Market Demand Requirements
<img width="832" height="430" alt="image" src="https://github.com/user-attachments/assets/c8770738-3cab-44b8-b956-aa47359efc6c" />
*1. Market Demand Forecast by End-Item — Image by Author*


* **Components:** Weekly sales forecast per finished end-item.
* **Assumption:** Demand is deterministic over a 15-week planning horizon, allowing the model to focus purely on supply-side uncertainty.
* **For instance:** Finished Item 'F' sees a massive demand spike in week 6, requiring the model to pre-position components 2–4 weeks in advance.

### 2. Component Holding Costs (Working Capital)
<img width="793" height="426" alt="image" src="https://github.com/user-attachments/assets/8c74ce19-51ef-4a33-b2d3-3cfc6c395295" />

*2. Component Holding Costs — Image by Author*

* **Components:** Cost of tied-up capital, insurance, and risk of obsolescence.
* **Assumption:** High-value components (e.g., CPUs) carry a high weekly "penalty," while low-value parts (e.g., fasteners) are cheap to store.
* **For instance:** Storing Component 16 costs $10.00/unit/week, making it a primary candidate for Just-In-Time (JIT) ordering to protect cash flow.

### 3. Bill of Materials (BOM) & Product Structure
<img width="811" height="419" alt="image" src="https://github.com/user-attachments/assets/64f86f4e-f083-4256-b021-b9778a0daf27" />
*3. Bill of Materials (BOM) Mapping — Image by Author*

* **Components:** Mapping of finished goods to their sub-assembly components.
* **Assumption:** An end-item is only "shippable" if 100% of its required components are available; otherwise, the entire order is canceled.
* **For instance:** Assembling 1 unit of Item 'I' requires a "kit" of 3 units of Component 1 and 4 units of Component 3. If either part is missing, the build fails.

### 4. Stochastic Lead Times (Supplier Reliability)
<img width="626" height="329" alt="image" src="https://github.com/user-attachments/assets/560b35c8-556e-42ac-b3f6-2efdcdcd7fe1" />
*4. Lead Time Probability Distributions Extract for 5 Components — Image by Author*

* **Components:** Probability distributions of delivery times per supplier.
* **Assumption:** Instead of a fixed 2-week arrival, each supplier has a unique probability of being early, on time, or dangerously late.
* **For instance:** Component 1 has a "long-tail" risk. While it usually arrives in 1 week, there is a 15% probability of a 5-week delay, creating the potential for a total system stock-out.

---

## 🚀 The Solution

Here are the results comparing the service level performance of the two planning methods:

<img width="506" height="404" alt="image" src="https://github.com/user-attachments/assets/0fea7add-65ed-42c2-98a0-da4125b9296d" />
<img width="581" height="472" alt="image" src="https://github.com/user-attachments/assets/5bd1749b-b4a8-46ab-939b-de7c33dcc626" />


We can see the **Stochastic method** (where we integrate uncertainty) far outperforms the **Deterministic method** (classic ERP scheduling).

---

## 📈 From Math to Strategy: ROI on Supplier Collaboration

Ok, so now what? Stochastic scheduling is a better solution, but it is still an expensive one. In an ideal world of certainty, the holding cost would be minimal because we would order components so they arrive perfectly just-in-time.

**But what if we can collaborate with suppliers and improve their reliability? Which supplier yields the highest ROI?**

To answer this, we wrote a sensitivity analysis orchestrator that:
1. Loops through every single component.
2. Artificially reduces its lead-time variability by 50%.
3. Re-optimizes the system.
4. Tests it out-of-sample to calculate the exact financial savings.

<img width="557" height="745" alt="image" src="https://github.com/user-attachments/assets/3f901f31-ed60-4b58-b106-52d27d1c4b07" />


### Key Takeaways
* **High ROI Intervention:** We can see that working with the supplier of **Component 3 (C3)** to improve their precision is highly lucrative. We could offer a $20,000 bonus over a 10-week plan, which would net us **$47,600 a year in savings!**
* **The Variability Paradox:** However, other parts of the results are surprising! Why does improving lead time precision sometimes *increase* our costs? Because in this simulation, as we reduced the variability, we also reduced the chances of having *shorter* lead times (early arrivals that naturally buffered the system).

## 💻 Explore the Code & Data

Want to see exactly how the stochastic linear programming model was built, or run the sensitivity analysis yourself? All the code and datasets used for this project are open-source and available in this repository.

* 📂 **Data:** Check out the [`main/`](DATA_ATO.xlsx/) for the raw CSV files containing the BOM, holding costs, lead time probability distributions, and demand forecasts.
* 🛠️ **Code:** The optimization model, data processing, and sensitivity analysis orchestrator can be found in the [`main/`](code/) (or specify your `.py` files here). 

Feel free to clone the repo, play around with the supplier parameters, and see how the holding costs change!
