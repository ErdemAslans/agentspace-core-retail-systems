# main.py - Suvari Pricing Intelligence Analytics
# Functions Framework based Cloud Function
# Version: 2.0 - Production Ready

import os
import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import statistics
import functions_framework
from google.cloud import bigquery

# =======================
# Configuration
# =======================
PROJECT_ID = "agentspace-ngc"
BQ_LOCATION = "europe-west1"
DATASET = "suvari_pricing"

# Corrected Table References (matching BigQuery exactly)
TABLES = {
    "competitor_tracking": f"`{PROJECT_ID}.{DATASET}.competitor_tracking`",
    "campaign_performance": f"`{PROJECT_ID}.{DATASET}.campaign_performance`", 
    "price_elasticity": f"`{PROJECT_ID}.{DATASET}.price_elasticity`",
    "promotional_calendar": f"`{PROJECT_ID}.{DATASET}.promotional_calendar`"
}

# Business Constants
@dataclass
class SuvariPricingMetrics:
    # Market regions from actual data
    MARKET_REGIONS = ['Turkey', 'Germany', 'Russia', 'Kazakhstan', 'Ukraine', 'Romania']
    PRICE_TIERS = ['Budget', 'Standard', 'Premium', 'Luxury']
    CAMPAIGN_TYPES = ['Bundle', 'Individual', 'Flash', 'Seasonal', 'Gift', 'Student']
    
    # Performance thresholds
    ROI_EXCELLENT_THRESHOLD = 500.0
    ROI_GOOD_THRESHOLD = 300.0
    ELASTICITY_HIGH_THRESHOLD = 2.0
    ELASTICITY_LOW_THRESHOLD = 1.0
    
    # Competitive positioning
    PRICE_ADVANTAGE_THRESHOLD = -15.0  # % below competitors
    PRICE_DISADVANTAGE_THRESHOLD = 10.0  # % above competitors
    MARKET_SHARE_POSITIVE_IMPACT = ['Positive', 'Very Positive']
    
    # Campaign effectiveness
    UPLIFT_EXCELLENT_THRESHOLD = 40.0
    UPLIFT_GOOD_THRESHOLD = 30.0
    DISCOUNT_HIGH_THRESHOLD = 25.0

logger = logging.getLogger("suvari-pricing-intel")
logging.basicConfig(level=logging.INFO)

# =======================
# Query Intent Detection
# =======================
def detect_query_intent(question: str) -> str:
    """Detect pricing intelligence query intent"""
    
    q = (question or "").lower()
    
    patterns = {
        "competitor_tracking": [
            r"competitor|rakip|competition", r"price|fiyat|pricing", r"market|pazar",
            r"positioning|konum", r"comparison|karşılaştırma", r"advantage|avantaj"
        ],
        "campaign_performance": [
            r"campaign|kampanya|promotion", r"roi|kar|return", r"marketing|pazarlama", 
            r"discount|indirim", r"performance|başarı", r"effectiveness|etkinlik"
        ],
        "price_elasticity": [
            r"elasticity|elastikiyet|optimization", r"optimal|optimum", r"demand|talep",
            r"sensitivity|hassasiyet", r"revenue|gelir", r"margin|kar"
        ],
        "promotional_calendar": [
            r"calendar|takvim|schedule", r"planning|planlama", r"future|gelecek",
            r"budget|bütçe", r"timeline|zaman", r"seasonal|mevsimsel"
        ]
    }
    
    for intent, pattern_list in patterns.items():
        for pattern in pattern_list:
            if any(word in q for word in pattern.split("|")):
                logger.info(f"Detected intent: {intent}")
                return intent
    
    return "competitor_tracking"  # Default

# =======================
# SQL Query Functions
# =======================

def sql_competitor_tracking() -> Tuple[str, List]:
    """Comprehensive competitor price tracking and market positioning analysis"""
    
    sql = f"""
    WITH competitor_insights AS (
        SELECT 
            ct.tracking_date,
            ct.competitor,
            ct.product_category,
            ct.market,
            ct.suvari_price_usd,
            ct.competitor_price_usd,
            ct.price_gap_pct,
            ct.promotion_flag,
            ct.quality_comparison,
            ct.brand_positioning,
            ct.market_share_impact
        FROM {TABLES['competitor_tracking']} ct
        WHERE ct.tracking_date BETWEEN DATE('2024-12-14') AND DATE('2024-12-15')
    ),
    market_position AS (
        SELECT 
            market,
            product_category,
            COUNT(DISTINCT competitor) as competitors_tracked,
            AVG(price_gap_pct) as avg_price_gap_pct,
            COUNT(CASE WHEN market_share_impact IN ('Positive', 'Very Positive') THEN 1 END) as positive_positioning_count,
            COUNT(CASE WHEN promotion_flag = 'TRUE' THEN 1 END) as competitor_promotions_active,
            COUNT(CASE WHEN price_gap_pct <= {SuvariPricingMetrics.PRICE_ADVANTAGE_THRESHOLD} THEN 1 END) as price_advantages,
            COUNT(CASE WHEN price_gap_pct >= {SuvariPricingMetrics.PRICE_DISADVANTAGE_THRESHOLD} THEN 1 END) as price_disadvantages,
            AVG(suvari_price_usd) as avg_suvari_price,
            AVG(competitor_price_usd) as avg_competitor_price
        FROM competitor_insights
        GROUP BY market, product_category
    ),
    competitive_rankings AS (
        SELECT 
            ci.*,
            mp.competitors_tracked,
            mp.avg_price_gap_pct,
            mp.positive_positioning_count,
            mp.competitor_promotions_active,
            mp.price_advantages,
            mp.price_disadvantages,
            ROUND(mp.avg_suvari_price, 2) as market_avg_suvari_price,
            ROUND(mp.avg_competitor_price, 2) as market_avg_competitor_price,
            RANK() OVER (PARTITION BY ci.market ORDER BY ci.price_gap_pct ASC) as price_competitiveness_rank,
            RANK() OVER (ORDER BY ABS(ci.price_gap_pct)) as overall_competitiveness_rank
        FROM competitor_insights ci
        JOIN market_position mp ON ci.market = mp.market AND ci.product_category = mp.product_category
    )
    SELECT 
        tracking_date,
        competitor,
        product_category,
        market,
        suvari_price_usd,
        competitor_price_usd,
        ROUND(price_gap_pct, 1) as price_gap_pct,
        promotion_flag,
        quality_comparison,
        brand_positioning,
        market_share_impact,
        competitors_tracked,
        ROUND(avg_price_gap_pct, 1) as market_avg_price_gap,
        positive_positioning_count,
        competitor_promotions_active,
        price_advantages,
        price_disadvantages,
        market_avg_suvari_price,
        market_avg_competitor_price,
        price_competitiveness_rank,
        overall_competitiveness_rank,
        -- Competitive position assessments
        CASE 
            WHEN price_gap_pct <= -30.0 AND market_share_impact = 'Very Positive' THEN '🏆 Dominant Market Position'
            WHEN price_gap_pct <= {SuvariPricingMetrics.PRICE_ADVANTAGE_THRESHOLD} AND market_share_impact IN ('Positive', 'Very Positive') THEN '💰 Strong Price Advantage'
            WHEN price_gap_pct BETWEEN -15.0 AND 15.0 THEN '⚖️ Competitive Parity'
            WHEN price_gap_pct >= {SuvariPricingMetrics.PRICE_DISADVANTAGE_THRESHOLD} THEN '🔴 Price Disadvantage'
            ELSE '📊 Neutral Position'
        END as competitive_position,
        CASE
            WHEN promotion_flag = 'TRUE' AND price_gap_pct >= 0 THEN '⚠️ Competitor Promotional Pressure'
            WHEN promotion_flag = 'TRUE' THEN '🎯 Competitor Promo Activity'
            ELSE '📊 Standard Competitive Environment'
        END as promotional_environment,
        CASE
            WHEN quality_comparison = 'Superior' AND price_gap_pct <= 0 THEN '💎 Premium Value Proposition'
            WHEN quality_comparison = 'Superior' THEN '⭐ Quality Advantage'
            WHEN quality_comparison = 'Comparable' THEN '✅ Quality Parity'
            ELSE '📈 Quality Improvement Opportunity'
        END as value_proposition,
        CASE
            WHEN brand_positioning = 'Premium' AND market_share_impact = 'Very Positive' THEN '🏆 Premium Brand Leader'
            WHEN brand_positioning = 'Premium' THEN '💎 Premium Positioning'
            WHEN brand_positioning = 'Mid-tier' THEN '📊 Mid-tier Positioning'
            ELSE '📈 Market Position Development'
        END as brand_position_strength
    FROM competitive_rankings
    ORDER BY tracking_date DESC, ABS(price_gap_pct) DESC
    LIMIT @limit
    """
    
    params = [
        bigquery.ScalarQueryParameter("limit", "INT64", None)
    ]
    
    return sql, params

def sql_campaign_performance() -> Tuple[str, List]:
    """Marketing campaign ROI and performance analysis"""
    
    sql = f"""
    WITH campaign_metrics AS (
        SELECT 
            cp.campaign_date,
            cp.campaign_name,
            cp.campaign_type,
            cp.target_audience,
            cp.discount_pct,
            cp.original_price_usd,
            cp.campaign_price_usd,
            cp.units_sold,
            cp.revenue_generated,
            cp.campaign_cost,
            cp.roi_pct,
            cp.customer_acquisition,
            cp.repeat_purchase_rate,
            cp.market_segment
        FROM {TABLES['campaign_performance']} cp
        WHERE cp.campaign_date BETWEEN DATE('2024-12-14') AND DATE('2024-12-15')
    ),
    campaign_analysis AS (
        SELECT 
            campaign_type,
            target_audience,
            market_segment,
            COUNT(*) as campaigns_executed,
            AVG(roi_pct) as avg_roi_pct,
            AVG(discount_pct) as avg_discount_pct,
            SUM(revenue_generated) as total_revenue_generated,
            SUM(campaign_cost) as total_campaign_cost,
            SUM(customer_acquisition) as total_new_customers,
            AVG(repeat_purchase_rate) as avg_repeat_purchase_rate,
            SUM(units_sold) as total_units_sold,
            -- Calculate efficiency metrics
            SUM(revenue_generated) / NULLIF(SUM(campaign_cost), 0) as revenue_cost_ratio,
            SUM(customer_acquisition) / NULLIF(SUM(campaign_cost), 0) * 1000 as cost_per_acquisition_usd
        FROM campaign_metrics
        GROUP BY campaign_type, target_audience, market_segment
    ),
    campaign_rankings AS (
        SELECT 
            cm.*,
            ca.campaigns_executed,
            ROUND(ca.avg_roi_pct, 1) as segment_avg_roi,
            ROUND(ca.avg_discount_pct, 1) as segment_avg_discount,
            ROUND(ca.total_revenue_generated, 2) as segment_total_revenue,
            ROUND(ca.total_campaign_cost, 2) as segment_total_cost,
            ca.total_new_customers,
            ROUND(ca.avg_repeat_purchase_rate, 1) as segment_avg_repeat_rate,
            ca.total_units_sold,
            ROUND(ca.revenue_cost_ratio, 2) as segment_revenue_cost_ratio,
            ROUND(ca.cost_per_acquisition_usd, 2) as segment_cost_per_acquisition,
            RANK() OVER (ORDER BY ca.avg_roi_pct DESC) as roi_rank,
            RANK() OVER (ORDER BY ca.total_revenue_generated DESC) as revenue_rank,
            RANK() OVER (ORDER BY ca.cost_per_acquisition_usd ASC) as efficiency_rank
        FROM campaign_metrics cm
        JOIN campaign_analysis ca ON cm.campaign_type = ca.campaign_type 
            AND cm.target_audience = ca.target_audience 
            AND cm.market_segment = ca.market_segment
    )
    SELECT 
        campaign_date,
        campaign_name,
        campaign_type,
        target_audience,
        market_segment,
        discount_pct,
        original_price_usd,
        campaign_price_usd,
        units_sold,
        ROUND(revenue_generated, 2) as revenue_generated,
        ROUND(campaign_cost, 2) as campaign_cost,
        ROUND(roi_pct, 1) as roi_pct,
        customer_acquisition,
        ROUND(repeat_purchase_rate, 1) as repeat_purchase_rate,
        campaigns_executed,
        segment_avg_roi,
        segment_avg_discount,
        segment_total_revenue,
        segment_total_cost,
        total_new_customers,
        segment_avg_repeat_rate,
        total_units_sold,
        segment_revenue_cost_ratio,
        segment_cost_per_acquisition,
        roi_rank,
        revenue_rank,
        efficiency_rank,
        -- Campaign performance assessments
        CASE 
            WHEN roi_pct >= {SuvariPricingMetrics.ROI_EXCELLENT_THRESHOLD} THEN '🏆 Excellent Campaign ROI'
            WHEN roi_pct >= {SuvariPricingMetrics.ROI_GOOD_THRESHOLD} THEN '✅ Good Campaign Performance'
            WHEN roi_pct >= 200.0 THEN '📊 Average Campaign Performance'
            ELSE '📉 Poor Campaign Performance'
        END as campaign_performance_tier,
        CASE
            WHEN discount_pct >= {SuvariPricingMetrics.DISCOUNT_HIGH_THRESHOLD} AND roi_pct >= {SuvariPricingMetrics.ROI_GOOD_THRESHOLD} THEN '💰 High Discount High Return'
            WHEN discount_pct >= {SuvariPricingMetrics.DISCOUNT_HIGH_THRESHOLD} THEN '🔴 High Discount Low Return'
            WHEN roi_pct >= {SuvariPricingMetrics.ROI_GOOD_THRESHOLD} THEN '💎 Efficient Campaign'
            ELSE '📊 Standard Campaign'
        END as discount_efficiency,
        CASE
            WHEN repeat_purchase_rate >= 60.0 THEN '🔁 Excellent Customer Retention'
            WHEN repeat_purchase_rate >= 40.0 THEN '✅ Good Customer Retention'
            WHEN repeat_purchase_rate >= 25.0 THEN '📊 Standard Customer Retention'
            ELSE '📈 Low Customer Retention'
        END as retention_performance,
        CASE
            WHEN customer_acquisition >= 100 AND segment_cost_per_acquisition <= 50 THEN '🎯 Efficient Customer Acquisition'
            WHEN customer_acquisition >= 50 THEN '📈 Good Customer Acquisition'
            WHEN customer_acquisition >= 20 THEN '📊 Standard Acquisition'
            ELSE '📉 Low Acquisition Campaign'
        END as acquisition_effectiveness
    FROM campaign_rankings
    ORDER BY roi_pct DESC, revenue_generated DESC
    LIMIT @limit
    """
    
    params = [
        bigquery.ScalarQueryParameter("limit", "INT64", None)
    ]
    
    return sql, params

def sql_price_elasticity() -> Tuple[str, List]:
    """Price optimization and elasticity analysis"""
    
    sql = f"""
    WITH elasticity_analysis AS (
        SELECT 
            pe.analysis_date,
            pe.product_category,
            pe.market,
            pe.price_point_usd,
            pe.demand_quantity,
            pe.elasticity_coefficient,
            pe.customer_segment,
            pe.sensitivity_level,
            pe.optimal_price_usd,
            pe.revenue_impact_pct,
            pe.margin_impact_pct,
            pe.recommendation
        FROM {TABLES['price_elasticity']} pe
        WHERE pe.analysis_date BETWEEN DATE('2024-12-14') AND DATE('2024-12-15')
    ),
    optimization_insights AS (
        SELECT 
            market,
            product_category,
            customer_segment,
            AVG(elasticity_coefficient) as avg_elasticity_coefficient,
            COUNT(*) as price_points_tested,
            AVG(revenue_impact_pct) as avg_revenue_impact_pct,
            AVG(margin_impact_pct) as avg_margin_impact_pct,
            COUNT(CASE WHEN recommendation = 'Increase Price' THEN 1 END) as price_increase_recommendations,
            COUNT(CASE WHEN recommendation = 'Decrease Price' THEN 1 END) as price_decrease_recommendations,
            COUNT(CASE WHEN recommendation = 'Maintain Price' THEN 1 END) as maintain_price_recommendations,
            AVG(optimal_price_usd) as avg_optimal_price,
            MAX(revenue_impact_pct) as max_revenue_impact,
            MIN(revenue_impact_pct) as min_revenue_impact
        FROM elasticity_analysis
        GROUP BY market, product_category, customer_segment
    ),
    price_rankings AS (
        SELECT 
            ea.*,
            oi.avg_elasticity_coefficient,
            oi.price_points_tested,
            ROUND(oi.avg_revenue_impact_pct, 1) as segment_avg_revenue_impact,
            ROUND(oi.avg_margin_impact_pct, 1) as segment_avg_margin_impact,
            oi.price_increase_recommendations,
            oi.price_decrease_recommendations,
            oi.maintain_price_recommendations,
            ROUND(oi.avg_optimal_price, 2) as segment_avg_optimal_price,
            ROUND(oi.max_revenue_impact, 1) as segment_max_revenue_impact,
            ROUND(oi.min_revenue_impact, 1) as segment_min_revenue_impact,
            RANK() OVER (ORDER BY ABS(ea.revenue_impact_pct) DESC) as revenue_impact_rank,
            RANK() OVER (PARTITION BY ea.market ORDER BY ea.elasticity_coefficient DESC) as market_sensitivity_rank
        FROM elasticity_analysis ea
        JOIN optimization_insights oi ON ea.market = oi.market 
            AND ea.product_category = oi.product_category 
            AND ea.customer_segment = oi.customer_segment
    )
    SELECT 
        analysis_date,
        product_category,
        market,
        customer_segment,
        price_point_usd,
        demand_quantity,
        ROUND(elasticity_coefficient, 2) as elasticity_coefficient,
        sensitivity_level,
        optimal_price_usd,
        ROUND(revenue_impact_pct, 1) as revenue_impact_pct,
        ROUND(margin_impact_pct, 1) as margin_impact_pct,
        recommendation,
        ROUND(avg_elasticity_coefficient, 2) as segment_avg_elasticity,
        price_points_tested,
        segment_avg_revenue_impact,
        segment_avg_margin_impact,
        price_increase_recommendations,
        price_decrease_recommendations,
        maintain_price_recommendations,
        segment_avg_optimal_price,
        segment_max_revenue_impact,
        segment_min_revenue_impact,
        revenue_impact_rank,
        market_sensitivity_rank,
        -- Elasticity and optimization assessments
        CASE 
            WHEN elasticity_coefficient >= {SuvariPricingMetrics.ELASTICITY_HIGH_THRESHOLD} THEN '🔴 Highly Price Sensitive'
            WHEN elasticity_coefficient >= {SuvariPricingMetrics.ELASTICITY_LOW_THRESHOLD} THEN '⚠️ Moderately Price Sensitive'
            ELSE '💎 Low Price Sensitivity'
        END as sensitivity_classification,
        CASE
            WHEN recommendation = 'Increase Price' AND revenue_impact_pct > 5 THEN '📈 Strong Price Increase Opportunity'
            WHEN recommendation = 'Increase Price' THEN '💰 Price Increase Opportunity'
            WHEN recommendation = 'Decrease Price' AND revenue_impact_pct > 10 THEN '🎯 Strategic Price Decrease'
            WHEN recommendation = 'Decrease Price' THEN '📉 Price Reduction Recommended'
            ELSE '⚖️ Maintain Current Pricing'
        END as pricing_strategy,
        CASE
            WHEN ABS(revenue_impact_pct) >= 15.0 THEN '🚀 High Revenue Impact Potential'
            WHEN ABS(revenue_impact_pct) >= 10.0 THEN '📈 Significant Revenue Impact'
            WHEN ABS(revenue_impact_pct) >= 5.0 THEN '📊 Moderate Revenue Impact'
            ELSE '📉 Minimal Revenue Impact'
        END as revenue_opportunity_level,
        CASE
            WHEN optimal_price_usd > price_point_usd * 1.1 THEN '💰 Under-priced Product'
            WHEN optimal_price_usd < price_point_usd * 0.9 THEN '💸 Over-priced Product'
            ELSE '✅ Optimally Priced'
        END as price_optimization_status
    FROM price_rankings
    ORDER BY ABS(revenue_impact_pct) DESC, elasticity_coefficient DESC
    LIMIT @limit
    """
    
    params = [
        bigquery.ScalarQueryParameter("limit", "INT64", None)
    ]
    
    return sql, params

def sql_promotional_calendar() -> Tuple[str, List]:
    """Promotional calendar planning and campaign scheduling"""
    
    sql = f"""
    WITH promotional_pipeline AS (
        SELECT 
            pc.promo_id,
            pc.start_date,
            pc.end_date,
            pc.campaign_name,
            pc.target_market,
            pc.product_category,
            pc.discount_type,
            pc.discount_value,
            pc.min_purchase_usd,
            pc.target_audience,
            pc.expected_uplift_pct,
            pc.budget_usd,
            pc.channel,
            pc.seasonality_factor,
            pc.competitive_response,
            DATE_DIFF(PARSE_DATE('%Y-%m-%d', pc.end_date), PARSE_DATE('%Y-%m-%d', pc.start_date), DAY) as campaign_duration_days
        FROM {TABLES['promotional_calendar']} pc
        WHERE PARSE_DATE('%Y-%m-%d', pc.start_date) >= DATE('2024-12-14')
    ),
    calendar_insights AS (
        SELECT 
            target_market,
            product_category,
            COUNT(*) as planned_campaigns,
            SUM(budget_usd) as total_market_budget,
            AVG(expected_uplift_pct) as avg_expected_uplift,
            AVG(discount_value) as avg_discount_value,
            AVG(campaign_duration_days) as avg_campaign_duration,
            COUNT(CASE WHEN competitive_response = 'High' THEN 1 END) as high_competition_campaigns,
            COUNT(CASE WHEN expected_uplift_pct >= {SuvariPricingMetrics.UPLIFT_EXCELLENT_THRESHOLD} THEN 1 END) as high_impact_campaigns,
            COUNT(DISTINCT channel) as channels_utilized,
            COUNT(DISTINCT target_audience) as audience_segments,
            MAX(expected_uplift_pct) as max_expected_uplift,
            MIN(budget_usd) as min_campaign_budget,
            MAX(budget_usd) as max_campaign_budget
        FROM promotional_pipeline
        GROUP BY target_market, product_category
    ),
    promo_rankings AS (
        SELECT 
            pp.*,
            ci.planned_campaigns,
            ROUND(ci.total_market_budget, 2) as market_total_budget,
            ROUND(ci.avg_expected_uplift, 1) as market_avg_expected_uplift,
            ROUND(ci.avg_discount_value, 1) as market_avg_discount,
            ROUND(ci.avg_campaign_duration, 0) as market_avg_duration_days,
            ci.high_competition_campaigns,
            ci.high_impact_campaigns,
            ci.channels_utilized,
            ci.audience_segments,
            ROUND(ci.max_expected_uplift, 1) as market_max_uplift,
            ROUND(ci.min_campaign_budget, 2) as market_min_budget,
            ROUND(ci.max_campaign_budget, 2) as market_max_budget,
            RANK() OVER (ORDER BY pp.expected_uplift_pct DESC, pp.budget_usd ASC) as impact_efficiency_rank,
            RANK() OVER (PARTITION BY pp.target_market ORDER BY pp.expected_uplift_pct DESC) as market_priority_rank
        FROM promotional_pipeline pp
        JOIN calendar_insights ci ON pp.target_market = ci.target_market AND pp.product_category = ci.product_category
    )
    SELECT 
        promo_id,
        start_date,
        end_date,
        campaign_name,
        target_market,
        product_category,
        discount_type,
        discount_value,
        min_purchase_usd,
        target_audience,
        expected_uplift_pct,
        budget_usd,
        channel,
        seasonality_factor,
        competitive_response,
        campaign_duration_days,
        planned_campaigns,
        market_total_budget,
        market_avg_expected_uplift,
        market_avg_discount,
        market_avg_duration_days,
        high_competition_campaigns,
        high_impact_campaigns,
        channels_utilized,
        audience_segments,
        market_max_uplift,
        market_min_budget,
        market_max_budget,
        impact_efficiency_rank,
        market_priority_rank,
        -- Campaign priority and impact assessments
        CASE 
            WHEN expected_uplift_pct >= {SuvariPricingMetrics.UPLIFT_EXCELLENT_THRESHOLD} AND budget_usd <= 20000 THEN '🚀 High Impact Low Cost'
            WHEN expected_uplift_pct >= {SuvariPricingMetrics.UPLIFT_EXCELLENT_THRESHOLD} THEN '⭐ High Impact Campaign'
            WHEN expected_uplift_pct >= {SuvariPricingMetrics.UPLIFT_GOOD_THRESHOLD} THEN '📈 Good Impact Campaign'
            WHEN expected_uplift_pct >= 20.0 THEN '📊 Moderate Impact Campaign'
            ELSE '📉 Low Impact Campaign'
        END as campaign_priority_tier,
        CASE
            WHEN competitive_response = 'High' AND expected_uplift_pct >= 35.0 THEN '⚔️ Competitive Battleground'
            WHEN competitive_response = 'High' THEN '⚠️ High Competitive Response Expected'
            WHEN competitive_response = 'Medium' THEN '📊 Moderate Competition'
            ELSE '✅ Low Competitive Pressure'
        END as competitive_intensity,
        CASE
            WHEN discount_type = 'Percentage' AND discount_value >= 30 THEN '💸 Deep Discount Strategy'
            WHEN discount_type = 'Fixed Amount' AND discount_value >= 200 THEN '💰 High Value Discount'
            WHEN discount_value >= 20 THEN '📊 Standard Discount'
            ELSE '💎 Premium Pricing Strategy'
        END as discount_strategy,
        CASE
            WHEN budget_usd >= 50000 THEN '💰 Major Campaign Investment'
            WHEN budget_usd >= 25000 THEN '💸 Significant Campaign Budget'
            WHEN budget_usd >= 10000 THEN '💵 Standard Campaign Budget'
            ELSE '💳 Limited Budget Campaign'
        END as budget_scale,
        CASE
            WHEN campaign_duration_days >= 30 THEN '📅 Extended Campaign Period'
            WHEN campaign_duration_days >= 14 THEN '🗓️ Standard Campaign Period'
            WHEN campaign_duration_days >= 7 THEN '⚡ Short Campaign Period'
            ELSE '🚀 Flash Campaign'
        END as duration_strategy
    FROM promo_rankings
    ORDER BY PARSE_DATE('%Y-%m-%d', start_date), expected_uplift_pct DESC
    LIMIT @limit
    """
    
    params = [
        bigquery.ScalarQueryParameter("limit", "INT64", None)
    ]
    
    return sql, params

# =======================
# Business Logic Layer
# =======================

def analyze_pricing_results(rows: List[Dict], query_type: str) -> Dict[str, Any]:
    """Generate pricing intelligence specific insights"""
    
    insights = []
    recommendations = []
    alerts = []
    
    if not rows:
        return {
            "insights": ["Belirtilen kriterlere uygun pricing verisi bulunamadı"],
            "recommendations": ["Tarih aralığını veya kriterleri genişletin"],
            "alerts": []
        }
    
    try:
        if query_type == "competitor_tracking":
            # Competitive position analysis
            strong_advantages = [r for r in rows if '💰 Strong Price Advantage' in str(r.get('competitive_position', ''))]
            price_disadvantages = [r for r in rows if '🔴 Price Disadvantage' in str(r.get('competitive_position', ''))]
            
            if strong_advantages:
                insights.append(f"💰 {len(strong_advantages)} kategoride güçlü fiyat avantajımız var")
            
            if price_disadvantages:
                alerts.append(f"🔴 {len(price_disadvantages)} kategoride fiyat dezavantajımız bulunuyor")
                recommendations.append("Fiyat dezavantajı olan kategorilerde strateji revizyonu yapın")
            
            # Market positioning insights
            premium_positions = [r for r in rows if '💎 Premium Value Proposition' in str(r.get('value_proposition', ''))]
            if premium_positions:
                insights.append(f"💎 {len(premium_positions)} kategoride premium değer önerisi sunuyoruz")
            
            # Promotional pressure analysis
            promo_pressure = [r for r in rows if '⚠️ Competitor Promotional Pressure' in str(r.get('promotional_environment', ''))]
            if promo_pressure:
                alerts.append(f"⚠️ {len(promo_pressure)} kategoride rakip promosyon baskısı var")
                recommendations.append("Rakip promosyonlarına karşı hızlı response stratejileri geliştirin")
            
            # Average price gap insight
            price_gaps = [r.get('price_gap_pct', 0) for r in rows if r.get('price_gap_pct') is not None]
            if price_gaps:
                avg_gap = sum(price_gaps) / len(price_gaps)
                if avg_gap < -10:
                    insights.append(f"📊 Ortalama fiyat avantajımız: %{abs(avg_gap):.1f} rakiplerden düşük")
                elif avg_gap > 10:
                    insights.append(f"📊 Ortalama fiyat dezavantajımız: %{avg_gap:.1f} rakiplerden yüksek")
                else:
                    insights.append(f"⚖️ Rakiplerle ortalama fiyat paritesi: %{avg_gap:.1f}")
        
        elif query_type == "campaign_performance":
            # ROI performance analysis
            excellent_roi = [r for r in rows if '🏆 Excellent Campaign ROI' in str(r.get('campaign_performance_tier', ''))]
            poor_performance = [r for r in rows if '📉 Poor Campaign Performance' in str(r.get('campaign_performance_tier', ''))]
            
            if excellent_roi:
                top_campaign = max(excellent_roi, key=lambda x: x.get('roi_pct', 0))
                insights.append(f"🏆 En başarılı kampanya: {top_campaign['campaign_name']} (ROI: %{top_campaign['roi_pct']})")
            
            if poor_performance:
                alerts.append(f"📉 {len(poor_performance)} kampanya düşük performans gösteriyor")
                recommendations.append("Düşük ROI'li kampanya tiplerini analiz edin ve optimize edin")
            
            # Customer acquisition effectiveness
            efficient_acquisition = [r for r in rows if '🎯 Efficient Customer Acquisition' in str(r.get('acquisition_effectiveness', ''))]
            if efficient_acquisition:
                insights.append(f"🎯 {len(efficient_acquisition)} kampanya verimli müşteri kazanımı sağlıyor")
            
            # Retention analysis
            excellent_retention = [r for r in rows if '🔁 Excellent Customer Retention' in str(r.get('retention_performance', ''))]
            if excellent_retention:
                insights.append(f"🔁 {len(excellent_retention)} kampanya mükemmel müşteri tutma oranı gösteriyor")
            
            # Overall performance metrics
            total_revenue = sum(r.get('revenue_generated', 0) for r in rows)
            total_cost = sum(r.get('campaign_cost', 0) for r in rows)
            if total_cost > 0:
                overall_roi = (total_revenue / total_cost - 1) * 100
                insights.append(f"📊 Toplam kampanya ROI: %{overall_roi:.1f}")
        
        elif query_type == "price_elasticity":
            # Pricing opportunities
            price_increase_opps = [r for r in rows if '📈 Strong Price Increase Opportunity' in str(r.get('pricing_strategy', ''))]
            under_priced = [r for r in rows if '💰 Under-priced Product' in str(r.get('price_optimization_status', ''))]
            
            if price_increase_opps:
                insights.append(f"📈 {len(price_increase_opps)} kategoride güçlü fiyat artırım fırsatı")
                recommendations.append("Fiyat artırım fırsatlarını değerlendirin ve pilot testler yapın")
            
            if under_priced:
                insights.append(f"💰 {len(under_priced)} ürün kategori optimal fiyatın altında")
                recommendations.append("Under-priced kategorilerde fiyat optimizasyonu yapın")
            
            # Sensitivity insights
            high_revenue_impact = [r for r in rows if '🚀 High Revenue Impact Potential' in str(r.get('revenue_opportunity_level', ''))]
            if high_revenue_impact:
                insights.append(f"🚀 {len(high_revenue_impact)} kategori yüksek gelir etkisi potansiyeli taşıyor")
                recommendations.append("Yüksek etki potansiyelli kategorilerde A/B testleri başlatın")
            
            # Market sensitivity analysis
            low_sensitivity = [r for r in rows if '💎 Low Price Sensitivity' in str(r.get('sensitivity_classification', ''))]
            if low_sensitivity:
                insights.append(f"💎 {len(low_sensitivity)} kategori düşük fiyat hassasiyeti gösteriyor (premium fırsat)")
                recommendations.append("Düşük hassasiyetli kategorilerde premium pricing stratejileri değerlendirin")
        
        elif query_type == "promotional_calendar":
            # High impact campaigns
            high_impact_low_cost = [r for r in rows if '🚀 High Impact Low Cost' in str(r.get('campaign_priority_tier', ''))]
            high_impact = [r for r in rows if '⭐ High Impact Campaign' in str(r.get('campaign_priority_tier', ''))]
            
            if high_impact_low_cost:
                insights.append(f"🚀 {len(high_impact_low_cost)} kampanya yüksek etki düşük maliyet kategorisinde")
                recommendations.append("High impact low cost kampanyaları öncelikle execute edin")
            
            insights.append(f"⭐ Toplam {len(high_impact + high_impact_low_cost)} yüksek etkili kampanya planlandı")
            
            # Competitive intensity
            competitive_battlegrounds = [r for r in rows if '⚔️ Competitive Battleground' in str(r.get('competitive_intensity', ''))]
            if competitive_battlegrounds:
                alerts.append(f"⚔️ {len(competitive_battlegrounds)} kampanya yoğun rekabetli ortamda")
                recommendations.append("Yoğun rekabetli kampanyalar için diferansiyasyon stratejileri geliştirin")
            
            # Budget allocation insights
            total_budget = sum(r.get('budget_usd', 0) for r in rows)
            major_investments = [r for r in rows if '💰 Major Campaign Investment' in str(r.get('budget_scale', ''))]
            
            insights.append(f"💰 Toplam planlanan kampanya bütçesi: ${total_budget:,.0f}")
            if major_investments:
                insights.append(f"💰 {len(major_investments)} major investment kampanyası planlandı")
            
            # Timeline insights
            flash_campaigns = [r for r in rows if '🚀 Flash Campaign' in str(r.get('duration_strategy', ''))]
            extended_campaigns = [r for r in rows if '📅 Extended Campaign Period' in str(r.get('duration_strategy', ''))]
            
            if flash_campaigns:
                insights.append(f"🚀 {len(flash_campaigns)} flash kampanya planlandı")
            if extended_campaigns:
                insights.append(f"📅 {len(extended_campaigns)} uzun dönemli kampanya planlandı")
    
    except Exception as e:
        logger.error(f"Error in analyze_pricing_results: {str(e)}")
    
    return {
        "insights": insights[:10],
        "recommendations": recommendations[:5],
        "alerts": alerts[:5]
    }

def calculate_pricing_summary(rows: List[Dict], query_type: str) -> Dict[str, Any]:
    """Calculate pricing intelligence summary statistics"""
    
    if not rows:
        return {"total_records": 0}
    
    summary = {
        "total_records": len(rows),
        "query_type": query_type,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        if query_type == "competitor_tracking":
            summary.update({
                "unique_competitors": len(set(r.get('competitor') for r in rows)),
                "unique_markets": len(set(r.get('market') for r in rows)),
                "avg_price_gap": sum(r.get('price_gap_pct', 0) for r in rows) / len(rows) if rows else 0,
                "competitive_advantages": len([r for r in rows if r.get('price_gap_pct', 0) <= -15])
            })
        
        elif query_type == "campaign_performance":
            summary.update({
                "unique_campaigns": len(set(r.get('campaign_name') for r in rows)),
                "total_revenue": sum(r.get('revenue_generated', 0) for r in rows),
                "total_cost": sum(r.get('campaign_cost', 0) for r in rows),
                "avg_roi": sum(r.get('roi_pct', 0) for r in rows) / len(rows) if rows else 0
            })
        
        elif query_type == "price_elasticity":
            summary.update({
                "price_points_analyzed": len(rows),
                "unique_markets": len(set(r.get('market') for r in rows)),
                "avg_elasticity": sum(r.get('elasticity_coefficient', 0) for r in rows) / len(rows) if rows else 0,
                "price_increase_opportunities": len([r for r in rows if r.get('recommendation') == 'Increase Price'])
            })
        
        elif query_type == "promotional_calendar":
            summary.update({
                "planned_campaigns": len(rows),
                "total_budget": sum(r.get('budget_usd', 0) for r in rows),
                "avg_expected_uplift": sum(r.get('expected_uplift_pct', 0) for r in rows) / len(rows) if rows else 0,
                "unique_markets": len(set(r.get('target_market') for r in rows))
            })
    
    except Exception as e:
        logger.error(f"Error in calculate_pricing_summary: {str(e)}")
    
    return summary

# =======================
# Main HTTP Handler
# =======================

@functions_framework.http
def pricing_intel_query(request):
    """Suvari Pricing Intelligence Analytics Engine"""
    
    try:
        # Parse request
        body = request.get_json(silent=True) or {}
        
        # Extract parameters
        question = body.get("question", "")
        query_type = body.get("query_type") or detect_query_intent(question)
        limit = min(int(body.get("limit", 100)), 500)
        
        logger.info(f"Processing pricing intel query - Type: {query_type}")
        
        # Query function mapping
        query_functions = {
            "competitor_tracking": sql_competitor_tracking,
            "competitor_analysis": sql_competitor_tracking,
            "campaign_performance": sql_campaign_performance,
            "campaign_analysis": sql_campaign_performance,
            "price_elasticity": sql_price_elasticity,
            "price_optimization": sql_price_elasticity,
            "promotional_calendar": sql_promotional_calendar,
            "promotional_planning": sql_promotional_calendar
        }
        
        # Get appropriate query
        query_func = query_functions.get(query_type, sql_competitor_tracking)
        sql, params = query_func()
        
        # Fill parameters
        filled_params = []
        for p in params:
            if p.name == "limit":
                filled_params.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
            else:
                filled_params.append(p)
        
        # Execute query
        client = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)
        job_config = bigquery.QueryJobConfig(
            query_parameters=filled_params,
            maximum_bytes_billed=5 * 1024 * 1024 * 1024,  # 5GB limit
            labels={"agent": "pricing_intel", "query_type": query_type}
        )
        
        job = client.query(sql, job_config=job_config)
        rows = [dict(r) for r in job.result()]
        
        # Analyze results
        analysis = analyze_pricing_results(rows, query_type)
        summary = calculate_pricing_summary(rows, query_type)
        
        # Build response
        response = {
            "success": True,
            "agent": "pricing_intel",
            "query_type": query_type,
            "parameters": {
                "limit": limit
            },
            "summary": summary,
            "insights": analysis["insights"],
            "recommendations": analysis["recommendations"],
            "alerts": analysis["alerts"],
            "row_count": len(rows),
            "rows": rows,
            "metadata": {
                "bytes_processed": job.total_bytes_processed,
                "bytes_billed": job.total_bytes_billed,
                "cache_hit": job.cache_hit,
                "dataset": DATASET,
                "location": BQ_LOCATION
            }
        }
        
        return (json.dumps(response, ensure_ascii=False, default=str), 200, {"Content-Type": "application/json"})
        
    except Exception as e:
        logger.exception(f"Pricing intel query failed: {str(e)}")
        error_response = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "agent": "pricing_intel",
            "query_type": query_type if 'query_type' in locals() else "unknown"
        }
        return (json.dumps(error_response, ensure_ascii=False), 500, {"Content-Type": "application/json"})