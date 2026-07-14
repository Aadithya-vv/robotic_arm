# Shared Architectural Contracts

## Document Control

| Field | Value |
|---|---|
| Package | Repository-level Contracts |
| Version | 1.0 |
| Status | Approved and Frozen — Engineering Mode |
| Scope | Cross-Engine architectural data conventions |
| Classification | Contract package; not an Engine and not an implementation API |

## Purpose

This document defines the shared semantic structure used at Engine contract boundaries. It defines meaning, required information, and invariants without prescribing programming-language types, serialization syntax, transport, storage, or algorithms.

## Contract Envelope

Every cross-Engine request and response shall use a versioned envelope containing identity, correlation, metadata, status, and payload information appropriate to the contract. Engines may extend metadata only through documented, backward-compatible contract evolution.

## Request Structure

An architectural request contains:

- **request identity:** a unique identity for the request instance;
- **contract identity and version:** the contract being invoked and the semantic version understood by the sender;
- **source identity:** the requesting Engine or approved user/system boundary;
- **target capability:** the owned capability being requested, not a concrete implementation;
- **correlation ID:** the end-to-end workflow correlation identity;
- **causation identity:** the immediately preceding request, event, or decision when applicable;
- **timestamp/context:** ordering and diagnostic context suitable for local execution;
- **metadata:** trace, provenance, validation, approval, and extension information;
- **payload:** the contract-specific semantic input;
- **expectation:** whether a response is required and any approved lifecycle constraint.

A request shall be rejected if its identity, contract version, source, required metadata, or payload validity cannot be established.

## Response Structure

An architectural response contains:

- **response identity:** a unique identity for the response instance;
- **request identity and correlation ID:** references to the request and workflow being answered;
- **contract identity and version:** the semantic contract used for the outcome;
- **source identity:** the responding Engine or approved boundary;
- **status:** the outcome under the shared status conventions;
- **metadata:** trace, provenance, validation, and extension information;
- **payload:** the valid result, partial result when explicitly permitted, or no result;
- **errors:** zero or more structured errors;
- **completion context:** timing and terminal/non-terminal classification when applicable.

A response shall never present failed, rejected, cancelled, or partial work as successful completion.

## Identity

Identities shall be unique within their declared scope, stable for the lifetime of the represented item, opaque to consumers, and independent of concrete storage or implementation. Engine identity uses the approved ENG identifier. Domain objects, requests, responses, explanations, plans, TaskIR artifacts, approval tokens, and update requests require distinct identity classes even if an implementation later uses a common representation.

## Correlation ID

The correlation ID links activity belonging to one end-to-end workflow across Engine boundaries. It shall be preserved unchanged through derived requests, responses, events, explanations, approval tokens, Semantic Plans, TaskIR, execution activity, replay, feedback, and runtime reports. Correlation does not grant authorization and does not replace object identity.

## Metadata

Shared metadata may express:

- originating Engine or user/system boundary;
- creation and observation context;
- provenance and source references;
- validation state and validator identity;
- explanation references;
- approval-token reference where execution approval is required;
- contract capabilities and extension declarations;
- safe diagnostic and trace context.

Metadata shall not conceal required contract fields, carry concrete implementation objects, or become an undocumented control channel.

## Versioning

Contracts use semantic major, minor, and patch meaning:

- **major:** incompatible semantic or required-structure change;
- **minor:** backward-compatible optional capability or field addition;
- **patch:** clarification that does not alter semantic compatibility.

Senders declare the produced contract version. Receivers validate compatibility before processing. Unsupported major versions are rejected explicitly. Silent coercion between incompatible versions is prohibited.

## Error Model

An architectural error contains:

- stable error category and code;
- human-readable summary safe for the receiving boundary;
- originating Engine or boundary;
- request/correlation references;
- recoverability classification;
- retry guidance only when retry is safe and approved;
- structured context that does not expose sensitive or concrete internal state;
- causal error references when a dependency error is propagated.

Shared error categories include validation, unsupported version, invalid state, dependency unavailable, timeout/communication, authorization/approval, conflict, cancelled, processing failure, and internal invariant failure. Engines may define owned subcategories without changing shared meanings.

## Status Conventions

| Status | Meaning |
|---|---|
| Accepted | Request is valid and owned processing may begin; not completion. |
| In Progress | Owned processing is active; not a terminal outcome. |
| Succeeded | Processing completed and the result passed required validation. |
| Partial | An explicitly permitted incomplete result exists; never equivalent to success. |
| Rejected | Request failed preconditions, validation, compatibility, or approval checks. |
| Failed | Accepted processing could not complete because of an owned or dependency failure. |
| Cancelled | Processing ended through an approved cancellation path. |

Only Succeeded is successful terminal completion. Partial requires explicit consumer handling. Rejected, Failed, and Cancelled are terminal unless a new request is submitted.

## Explanation Record

Every Engine produces explanation records for its own important decisions and transitions. An explanation record contains its identity, producing Engine, correlation/provenance references, subject, decision or transition, supporting facts, validation/status context, and human-readable meaning. ENG-016 aggregates, links, formats, and exposes these records. ENG-020 displays the exposed explanations. ENG-016 shall not invent or alter an Engine's owned reasoning, and ENG-020 shall not become an explanation owner.

## Semantic Plan

A Semantic Plan is the sole planning output owned by ENG-015. It represents an interpreted task intent, goal, semantic entities and roles, ordered or dependency-constrained semantic actions, preconditions, postconditions, constraints, planning rationale, validation state, provenance, identity, version, and correlation information. It is not TaskIR and contains no simulator-specific syntax.

## Knowledge Update Request

A Knowledge Update Request is produced by ENG-022 from validated feedback. It contains request identity, correlation/provenance, the proposed semantic correction or validation, supporting user-feedback evidence, affected knowledge references, and validation context. ENG-022 never applies or stores the knowledge mutation. ENG-012 validates the request against Knowledge ownership rules and either applies it or returns an explicit rejection/failure outcome.

## Approval Token

An Approval Token is owned and issued by ENG-020 after explicit user approval of the exact execution subject. It contains token identity, user-approval evidence reference, approved TaskIR identity and version, correlation ID, issuance context, validity constraints, and status. ENG-017 consumes and validates the token before execution. A token is bound to one TaskIR identity/version and correlation context; it cannot authorize modified or unrelated TaskIR. ENG-017 shall never create, infer, refresh, or self-approve a token.

## Contract Governance

All Engines depend on these meanings through contracts, not concrete implementations. Changes require architecture review and versioning. This package does not define APIs, classes, wire formats, storage, cryptography, UI behavior, or algorithms.

