# RULE — Prefer Declarative Mapping Over Conditional Logic

**ID:** `CORE-DESIGN-001`  
**Priority:** HIGH  
**Scope:** All programming languages  
**Category:** Clean Code / Architecture / Maintainability

## Principle

Prefer declarative, data-driven mappings over repetitive conditional statements
when associating input values with predefined outputs or behaviors.
Use the most idiomatic construct supported by the programming language.

## Mandatory Guidelines

1. **Prefer mapping over conditions:** Starting from 2 simple value-to-result
   branches, prioritize a lookup table, map, dictionary, object mapping or
   equivalent native construct when it improves clarity.
2. **Centralize business rules:** Define related mappings in clearly named
   structures instead of scattering them across conditional branches.
3. **Use explicit fallbacks:** Define predictable behavior for unknown, missing
   or unsupported values.
4. **Preserve precedence:** When multiple mapping sources exist, maintain their
   evaluation priority and resolution order.
5. **Separate responsibilities:** Use distinct mappings for different business
   domains or resolution criteria.
6. **Avoid unnecessary branching:** Do not use repetitive `if / else if`,
   `switch / case` or equivalent structures when a simple lookup is sufficient.
7. **Preserve behavior:** Refactoring must not change outputs, side effects,
   error handling, type contracts or business rules.
8. **Avoid overengineering:** Do not introduce unnecessary factories,
   inheritance, polymorphism or Strategy Patterns when a native mapping
   structure solves the problem.
9. **Prefer immutability:** Treat static mapping definitions as immutable
   whenever the language supports it.
10. **Ensure testability:** Cover known keys, unknown keys, default behavior,
    precedence and edge cases with appropriate tests.

## Language-Agnostic Decision Rule

- **IF** multiple conditions compare the same input against predefined values
  and produce fixed outputs, **THEN** prefer a declarative mapping using the
  language's idiomatic lookup mechanism.
- **ELSE IF** branches execute distinct behaviors, **THEN** evaluate function
  dispatch or a language-native equivalent.
- **ELSE IF** conditions involve complex business predicates, ranges, state
  transitions or side effects, **THEN** retain explicit conditional logic or
  choose a more appropriate abstraction.

A mapping must preserve the language's equality and key semantics, evaluation
order and lazy execution. Do not eagerly execute unselected behaviors or
fallbacks, collapse distinct inputs or replace a valid falsy result with a
fallback. Retain conditionals when a lookup would obscure intent or alter these
semantics; two branches trigger evaluation, not an automatic conversion.

## Agent Enforcement

During planning, implementation, refactoring and code review, the agent MUST:

- Identify repetitive conditional chains in the affected scope.
- Evaluate whether declarative mappings provide a clearer solution.
- Prefer native language constructs over custom abstractions.
- Preserve business logic and execution semantics.
- Avoid unnecessary complexity.
- Verify behavioral equivalence through tests.

Apply this rule to all languages, including Python, TypeScript, JavaScript,
Java, Go and Rust, without imposing a shared syntax or unrelated refactoring.

## Acceptance Criteria

- Mapping-based solutions are preferred when appropriate.
- Repetitive equality conditions are minimized.
- Business rules are centralized and explicit.
- Existing behavior is preserved.
- Code follows the conventions of the target language.
- No unnecessary abstraction is introduced.

## Core philosophy

Declarative over imperative when appropriate.  
Data-driven over repetitive branching.  
Simplicity over abstraction.  
Readability and correctness over brevity.
