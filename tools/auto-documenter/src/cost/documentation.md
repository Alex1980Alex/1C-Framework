# Code Documentation

This directory contains modules for tracking and managing costs associated with Large Language Model (LLM) API usage.

## `cost-tracker.ts`

This module provides functionality to track and summarize the costs incurred by LLM requests. It allows for per-request cost recording, aggregation of statistics by provider, and budget monitoring.

### Key Components:

*   **Interfaces:**
    *   `RequestCost`: Defines the structure for tracking the cost of a single LLM request.
    *   `ProviderCostStats`: Aggregates cost and token usage statistics for a specific LLM provider.
    *   `CostSummary`: Provides a comprehensive overview of all tracked costs for a session.
    *   `BudgetLimit`: Defines configurable limits for cost, tokens, and requests.
    *   `BudgetStatus`: Reports on the current state of budget adherence, including warnings and exceedances.
*   **`CostTracker` Class:**
    *   Manages the collection and aggregation of cost data.
    *   `constructor(budgetLimit?: BudgetLimit)`: Initializes the tracker, optionally with budget limits.
    *   `recordRequest(provider: Provider, model: string, inputTokens: number, outputTokens: number)`: Records a single LLM request, calculates its cost, and updates statistics.
    *   `getSummary(): CostSummary`: Returns a summary of all tracked costs and usage.
    *   `getProviderStats(provider: Provider)`: Retrieves detailed statistics for a specific provider.
    *   `checkBudget(): BudgetStatus`: Evaluates current usage against configured budget limits.
    *   `setBudgetLimit(budgetLimit: BudgetLimit)`: Updates the budget limits.
    *   `reset()`: Clears all tracked data.
    *   `printSummary()`: Outputs a formatted cost summary to the console.
    *   `exportToJSON()`: Exports the tracked cost data in JSON format.

## `pricing-config.ts`

This module defines the pricing structure for various LLM providers and models. It includes functions to retrieve pricing information, calculate costs, and check free tier status and daily limits.

### Key Components:

*   **Types:**
    *   `Provider`: An enumeration of supported LLM providers.
    *   `ModelPricing`: Defines the cost (per million tokens), free tier status, and optional daily limits for a specific model.
    *   `ProviderPricing`: Contains the default model and a map of all models for a given provider.
*   **`PRICING_CONFIG` Constant:** A comprehensive object mapping each `Provider` to its `ProviderPricing` configuration.
*   **Functions:**
    *   `getModelPricing(provider: Provider, model?: string)`: Retrieves the pricing details for a specified model from a given provider.
    *   `calculateCost(provider: Provider, model: string, inputTokens: number, outputTokens: number)`: Computes the cost in USD for a given request based on token counts and pricing.
    *   `isFreeModel(provider: Provider, model?: string)`: Determines if a model is designated as free.
    *   `getDailyLimits(provider: Provider, model?: string)`: Retrieves the daily request or token limits for a model.
    *   `formatCost(cost: number)`: Formats a numerical cost into a human-readable string (e.g., '$1.23', 'FREE').
    *   `printPricingInfo()`: Displays pricing details for all configured providers and models to the console.

### File Relationships:

*   `cost-tracker.ts` depends on `pricing-config.ts` to:
    *   Calculate the cost of individual requests using `calculateCost`.
    *   Determine if a model is free using `isFreeModel`.
    *   Retrieve model pricing details using `getModelPricing`.
    *   Access daily limits for free models using `getDailyLimits`.
    *   Format costs for display using `formatCost`.