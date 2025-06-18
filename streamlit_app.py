import streamlit as st
import pandas as pd

def calculate_swing_pricing(
    nav_per_share_gross,
    shares_outstanding,
    subscriptions_units,
    redemptions_units,
    explicit_cost_per_unit,
    implicit_bid_ask_per_unit,
    implicit_market_impact_per_unit,
    swing_method,
    swing_threshold_percent,
    max_swing_factor_limit_percent
):
    """
    Calculates the swung Net Asset Value (NAV) based on fund flows and estimated transaction costs.
    This function implements the core logic for swing pricing.
    """

    # Calculate total fund assets (before any swing adjustment)
    total_fund_assets = nav_per_share_gross * shares_outstanding

    # Calculate net flow in units
    net_flow_units = subscriptions_units - redemptions_units # [1, 2]

    # Determine if swing pricing should be applied (for partial swing)
    apply_swing = False
    net_flow_percentage = (abs(net_flow_units) / shares_outstanding) * 100 if shares_outstanding > 0 else 0

    if swing_method == "Full Swing": # [3, 4]
        apply_swing = True
    elif swing_method == "Partial Swing": # [3, 4]
        if net_flow_percentage > swing_threshold_percent: # [3, 5, 6]
            apply_swing = True

    # Calculate the total estimated transaction cost per unit of flow
    # Costs include explicit (brokerage, taxes) and implicit (bid-ask, market impact) [3]
    total_transaction_cost_per_unit_of_flow = explicit_cost_per_unit + implicit_bid_ask_per_unit + implicit_market_impact_per_unit

    # The adjustment to NAV per share is directly this total cost per unit of flow,
    # as per the formula C / (S-R) or C / (R-S) where C is total cost for net flow,
    # and (S-R) is net units, effectively giving cost per unit of net flow. [1, 2]
    nav_adjustment_per_share_raw = total_transaction_cost_per_unit_of_flow

    # Calculate the raw swing factor percentage based on this adjustment relative to gross NAV
    raw_swing_factor_percent = (nav_adjustment_per_share_raw / nav_per_share_gross) * 100 if nav_per_share_gross > 0 else 0

    # Apply the maximum swing factor limit (e.g., SEC's 2% limit) [7, 8]
    swing_factor_percent = min(raw_swing_factor_percent, max_swing_factor_limit_percent)

    # Calculate the swung NAV per share
    nav_per_share_swung = nav_per_share_gross
    if apply_swing and net_flow_units!= 0:
        # Apply the limited swing factor percentage to the gross NAV
        if net_flow_units > 0:  # Net subscriptions (inflow)
            nav_per_share_swung = nav_per_share_gross * (1 + swing_factor_percent / 100)
        else:  # Net redemptions (outflow)
            nav_per_share_swung = nav_per_share_gross * (1 - swing_factor_percent / 100)

    # Calculate dilution impact magnitude (benefit to existing shareholders)
    dilution_impact_per_share_magnitude = abs(nav_per_share_swung - nav_per_share_gross)
    dilution_impact_percent_magnitude = (dilution_impact_per_share_magnitude / nav_per_share_gross) * 100 if nav_per_share_gross > 0 else 0

    return {
        "nav_per_share_gross": nav_per_share_gross,
        "total_fund_assets": total_fund_assets,
        "net_flow_units": net_flow_units,
        "net_flow_percentage": net_flow_percentage,
        "total_transaction_cost_per_unit_of_flow": total_transaction_cost_per_unit_of_flow,
        "nav_adjustment_per_share_raw": nav_adjustment_per_share_raw,
        "raw_swing_factor_percent": raw_swing_factor_percent,
        "applied_swing_factor_percent": swing_factor_percent if apply_swing else 0.0,
        "apply_swing": apply_swing,
        "nav_per_share_swung": nav_per_share_swung,
        "dilution_impact_per_share_magnitude": dilution_impact_per_share_magnitude,
        "dilution_impact_percent_magnitude": dilution_impact_percent_magnitude
    }

# --- Streamlit App Layout ---
st.set_page_config(layout="wide", page_title="Swing Pricing Model for Asset Managers")

st.title("Swing Pricing Model for Asset Managers")
st.markdown(
    """
    This application demonstrates a simplified swing pricing model for asset managers,
    incorporating key concepts and calculations based on industry practices and regulatory considerations.
    It allows you to simulate the impact of fund flows and transaction costs on Net Asset Value (NAV)
    under different swing pricing methodologies.
    """
)

st.header("1. Fund Parameters & Daily Flows")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Fund Details")
    nav_per_share_gross = st.number_input(
        "Gross NAV per Share (before swing)",
        min_value=0.01,
        value=100.00,
        step=0.01,
        format="%.2f",
        help="The fund's Net Asset Value per share before any swing pricing adjustment. [3]"
    )
    shares_outstanding = st.number_input(
        "Total Shares Outstanding",
        min_value=1,
        value=1_000_000,
        step=1,
        help="Total number of shares currently issued by the fund."
    )

with col2:
    st.subheader("Daily Investor Activity")
    subscriptions_units = st.number_input(
        "Subscription Units (Inflows)",
        min_value=0,
        value=50000,
        step=1000,
        help="Total units subscribed by investors for the day. [3]"
    )
    redemptions_units = st.number_input(
        "Redemption Units (Outflows)",
        min_value=0,
        value=10000,
        step=1000,
        help="Total units redeemed by investors for the day. [3]"
    )

st.header("2. Estimated Transaction Costs")
st.markdown(
    """
    These costs are incurred when the fund buys or sells underlying securities to meet investor flows.
    They are categorized into explicit (direct) and implicit (indirect) costs. [3]
    """
)

col_costs1, col_costs2, col_costs3 = st.columns(3)

with col_costs1:
    explicit_cost_per_unit = st.number_input(
        "Explicit Cost per Unit (e.g., Brokerage, Taxes)",
        min_value=0.000,
        value=0.050,
        step=0.001,
        format="%.3f",
        help="Direct, quantifiable expenses like brokerage fees, market charges, and taxes per unit traded. [3]"
    )
with col_costs2:
    implicit_bid_ask_per_unit = st.number_input(
        "Implicit Cost per Unit (Bid-Ask Spread)",
        min_value=0.000,
        value=0.020,
        step=0.001,
        format="%.3f",
        help="Cost arising from the difference between bid and ask prices, not naturally captured in mid-point NAV. [3]"
    )
with col_costs3:
    implicit_market_impact_per_unit = st.number_input(
        "Implicit Cost per Unit (Market Impact)",
        min_value=0.000,
        value=0.030,
        step=0.001,
        format="%.3f",
        help="Adjustment for price movement caused by the trading activity itself, especially for large orders. [3]"
    )

st.header("3. Swing Pricing Methodology")

swing_method = st.radio(
    "Select Swing Pricing Method:",
    ("Partial Swing", "Full Swing"),
    help="""
    **Full Swing Pricing:** NAV is adjusted whenever there is any net flow. [3, 4]
    **Partial Swing Pricing:** NAV is adjusted only when net flow exceeds a predefined threshold. [3, 4]
    """
)

swing_threshold_percent = 0.0
if swing_method == "Partial Swing":
    swing_threshold_percent = st.slider(
        "Partial Swing Threshold (% of Shares Outstanding)",
        min_value=0.0,
        max_value=10.0,
        value=1.0,
        step=0.1,
        format="%.1f%%",
        help="The percentage of net flow (relative to shares outstanding) that triggers swing pricing. Common thresholds are 1%. [6, 9]"
    )

max_swing_factor_limit_percent = st.slider(
    "Maximum Swing Factor Limit (% of NAV)",
    min_value=0.0,
    max_value=5.0,
    value=2.0,
    step=0.1,
    format="%.1f%%",
    help="The upper limit on the swing factor, typically capped (e.g., SEC allows up to 2%). [7, 8]"
)

st.markdown("---")

# Perform calculations
results = calculate_swing_pricing(
    nav_per_share_gross,
    shares_outstanding,
    subscriptions_units,
    redemptions_units,
    explicit_cost_per_unit,
    implicit_bid_ask_per_unit,
    implicit_market_impact_per_unit,
    swing_method,
    swing_threshold_percent,
    max_swing_factor_limit_percent
)

st.header("4. Swing Pricing Calculation Results")

col_res1, col_res2, col_res3 = st.columns(3)

with col_res1:
    st.metric(label="Gross NAV per Share", value=f"${results['nav_per_share_gross']:.2f}")
    st.metric(label="Total Fund Assets (Gross)", value=f"${results['total_fund_assets']:,.2f}")
    st.metric(label="Net Flow (Units)", value=f"{results['net_flow_units']:,}")

with col_res2:
    st.metric(label="Net Flow (% of Shares)", value=f"{results['net_flow_percentage']:.2f}%")
    st.metric(label="Total Transaction Cost per Unit of Flow", value=f"${results['total_transaction_cost_per_unit_of_flow']:.3f}")
    st.metric(label="Raw Swing Factor (% of NAV)", value=f"{results['raw_swing_factor_percent']:.2f}%")

with col_res3:
    st.metric(label="Swing Pricing Applied?", value="Yes" if results['apply_swing'] else "No")
    st.metric(label="Applied Swing Factor (% of NAV)", value=f"{results['applied_swing_factor_percent']:.2f}%")
    st.metric(label="Swung NAV per Share", value=f"${results['nav_per_share_swung']:.2f}")

st.subheader("Dilution Impact Analysis")
st.info(
    f"The magnitude of the adjustment to the NAV reflects the estimated transaction costs "
    f"allocated to transacting investors, thereby protecting existing shareholders from dilution. [3, 7]"
)
col_dilution1, col_dilution2 = st.columns(2)
with col_dilution1:
    st.metric(label="Dilution Impact per Share (Magnitude)", value=f"${results['dilution_impact_per_share_magnitude']:.4f}")
with col_dilution2:
    st.metric(label="Dilution Impact Percentage (Magnitude)", value=f"{results['dilution_impact_percent_magnitude']:.4f}%")

st.header("5. Key Operational & Governance Considerations (from Research)")

st.markdown(
    """
    A full-service swing pricing application for asset managers goes beyond mere calculation.
    It requires robust features to address operational realities and regulatory requirements.
    """
)

with st.expander("Governance, Oversight, and Policy Frameworks"):
    st.markdown(
        """
        *   **Board Oversight:** The fund's board or equivalent governing body holds ultimate responsibility for approving swing pricing policies and procedures, including swing factor upper limits and thresholds. Annual reviews of policy adequacy and effectiveness are required. [3, 8, 10]
        *   **Documented Policy:** A clear, documented policy is essential, defining costs, methodologies, allocation rules, and review frequencies (at least twice a year for parameters). [3, 1, 11, 2, 12]
        *   **Investor Disclosure vs. Confidentiality:** Funds must disclose the use of swing pricing to investors (e.g., in registration statements like Form N-1A), but detailed thresholds or model specifications should remain confidential to prevent arbitrage. [3, 6, 8, 13]
        *   **Conflict of Interest Management:** Robust procedures are needed to identify and manage potential conflicts of interest, ensuring no investor gains unfair advantage. [1, 11, 2, 12]
        """
    )

with st.expander("Critical Data Flow and Timeliness"):
    st.markdown(
        """
        *   **Pre-NAV Flow Determination:** For daily-dealing funds, final net flow must be determined before NAV calculation to produce the "swung" NAV. [3]
        *   **Data Latency Challenge:** A major operational challenge is receiving timely and accurate daily fund flow information from intermediaries, often due to a "chicken-and-egg" conundrum where intermediaries need NAV before providing final flow data. [5, 14, 15]
        *   **Estimates & Reconciliation:** Regulators may permit "reasonable, high confidence estimates" for swing threshold determination when complete data isn't available. The system needs robust reconciliation tools. [14]
        *   **T+1 Settlement Impact:** The shift to T+1 settlement further compresses operational timelines, intensifying pressure on data processing and NAV calculation. [16, 15]
        """
    )

with st.expander("Model Management, Validation, and Back-Testing"):
    st.markdown(
        """
        *   **Oversight & Review:** Quantitative models for swing pricing require strong, continuous oversight, including standards for design, implementation, performance monitoring, and regular suitability reviews. [3]
        *   **Human Judgment:** Swing pricing is not fully automated; it requires significant human judgment and expertise from trading, portfolio management, and risk teams to supplement model outputs, especially during stressed market conditions. [3]
        *   **Back-Testing:** Applied swing factors must be back-tested against actual transaction costs to verify alignment and refine models. [3, 17]
        *   **Documentation:** All cost estimates must be thoroughly documented and supported by justifiable data, ensuring traceability and auditability. [1, 11, 2, 12]
        *   **Contingency Planning:** Asset managers need tested contingency plans and governance mechanisms to respond to rapid changes in market conditions and stress events. [3]
        """
    )

st.header("6. Disclaimer")
st.warning(
    """
    **Important Disclaimer:** This Streamlit application is a simplified conceptual model for educational and
    demonstration purposes only. It does not replicate the full complexity, regulatory rigor, or real-time
    data integration capabilities of a production-grade swing pricing system used by asset managers.
    Actual implementations require sophisticated data feeds, advanced quantitative models,
    extensive regulatory compliance features, robust audit trails, and seamless integration with
    existing fund accounting, order management, and trading platforms.
    """
)

# --- Feature: Show App Code ---
st.markdown("---") # Add a separator
st.header('App Source Code', divider='gray')

current_script_path = Path(__file__)

try:
    with open(current_script_path, 'r') as f:
        app_code = f.read()
    with st.expander("Click to view the Python code for this app"):
        st.code(app_code, language='python')
except Exception as e:
    st.error(f"Could not load app source code: {e}")
st.markdown("---")
st.markdown("Developed based on research into swing pricing mechanisms and regulatory guidelines.")
