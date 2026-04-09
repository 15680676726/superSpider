# Buddy Domain Carrier Split Design

## 0. Purpose

This spec fixes the remaining Buddy domain-truth gap:

- domain capability is already modeled per domain
- execution carrier is still shared globally per Buddy profile

That mismatch breaks the intended rebirth semantics for cross-domain switching.

The target is:

- one Buddy global identity
- one relationship layer
- one domain capability record per domain
- one execution carrier per domain capability record
- chat-driven domain expansion without carrier replacement
- page-driven hard domain switching with archive/restore semantics

This spec is a correction on top of the earlier `BuddyDomainCapabilityRecord` design.

---

## 1. Problem Statement

Today `start-new` creates a fresh `BuddyDomainCapabilityRecord`, but the runtime truth still reuses a single shared carrier:

- `industry_instance_id = buddy:{profile_id}`

Then the capability growth refresh reads planning and execution facts from that shared carrier and immediately rehydrates the new domain score with the old domain's evidence/history.

So the current system does **not** actually satisfy:

- cross-domain switch feels like rebirth in the current domain
- archived domain truth remains isolated and restorable

The root problem is not the stage label or the capability record itself.

The root problem is:

> capability truth is domain-scoped, but execution truth is still profile-scoped

---

## 2. Core Judgment

Buddy now needs three distinct layers, not two:

### 2.1 Global Buddy Layer

Profile-scoped and always preserved:

- `HumanProfile`
- `CompanionRelationship`
- Buddy name
- intimacy / affinity / mood / presence
- stable companionship memory

### 2.2 Domain Capability Layer

Domain-scoped Buddy ability truth:

- `BuddyDomainCapabilityRecord`
- capability score
- stage
- strategy / execution / evidence / stability progress

### 2.3 Domain Execution Carrier Layer

Runtime-scoped operating truth for that same domain:

- one formal execution carrier
- its lanes / backlog / cycles / assignments / reports / evidence
- its continuity handles
- its chat/control thread history

This means:

- relationship does not reset on domain switch
- capability is per domain
- runtime carrier is also per domain
- stage is derived only from the active domain's carrier facts

---

## 3. Domain Change Types

The system must stop treating every target change as the same thing.

There are three different changes:

### 3.1 Target Upgrade

Example:

- stock trading `10w -> 100w`

Meaning:

- same core domain
- same operating line
- goal difficulty increases

Handling:

- keep the same `BuddyDomainCapabilityRecord`
- keep the same execution carrier
- update target and planning facts only

### 3.2 Domain Expansion

Example:

- stock trading -> options
- writing -> course / IP
- fitness -> diet management

Meaning:

- still the same active domain
- the domain scope is getting wider or deeper
- this is not a hard reset

Handling:

- expansion happens through chat, not the page switch flow
- keep the same `BuddyDomainCapabilityRecord`
- keep the same execution carrier
- enrich domain scope/summary/tags rather than replacing the domain

### 3.3 Domain Switch

Example:

- stock trading -> writing

Meaning:

- the human wants to leave the current main line and move to a different domain

Handling:

- this is a page-level explicit action
- archive and freeze the old domain carrier
- switch to a matching archived domain carrier if restoring history
- otherwise create a fresh domain carrier and fresh capability record

---

## 4. UX Rule Split

### 4.1 Chat owns expansion

Buddy chat is the place where the active domain can broaden over time.

Chat may:

- capture new adjacent scope
- deepen the current line
- revise the domain summary
- widen the planning surface inside the current carrier

Chat must **not** silently create a new domain carrier.

### 4.2 Page owns hard switching

The onboarding/direction page becomes the explicit front-door for hard domain switching.

That page is where the human confirms:

- continue current domain
- restore archived domain
- start a brand-new domain

### 4.3 Cross-domain drift in chat

When chat content looks clearly outside the active domain:

- the system may detect and flag it
- the system may explain that this looks like a new main domain
- the system may recommend using the page switch flow

But the system must **not** auto-switch domains from chat.

The rule is:

> chat can expand the current domain, but only the page can replace the current domain

---

## 5. Formal State Change

`BuddyDomainCapabilityRecord` needs to own its carrier binding.

Recommended additional fields:

- `industry_instance_id`
- `control_thread_id` (or the canonical chat/control continuity reference already used by the runtime chain)
- `domain_scope_summary`
- `domain_scope_tags`

The important part is not the exact field names.

The important contract is:

- one active domain capability record points to one active domain carrier
- archived domain capability records point to their archived domain carriers
- restore means reactivating the same carrier, not reconstructing from scratch

If the existing continuity truth already lives elsewhere, `BuddyDomainCapabilityRecord` may store a stable foreign key rather than duplicate the continuity payload.

---

## 6. Carrier Lifecycle Rules

### 6.1 Active domain

Only one domain carrier may be active for a Buddy profile at a time.

The active domain carrier is the only carrier allowed to:

- receive current planning growth
- drive current stage growth
- appear as the current Buddy carrier in chat / Runtime Center

### 6.2 Archived domain

When a hard domain switch happens:

- the old domain carrier must be archived/frozen
- it must stop being the source for active capability growth
- it must stop continuing background progression as the current domain
- its history must remain intact for later restore

### 6.3 Restore archived domain

When the human returns to an old domain:

- reactivate the archived capability record
- reactivate the archived carrier
- restore the original chat/control continuity
- keep the preserved planning/evidence history

Restore is not "copy old score into a new carrier".

Restore is "make the previous domain chain active again".

---

## 7. Execution Carrier Contract

The current shared carrier identity:

- `buddy:{profile_id}`

is no longer sufficient.

The target contract is:

- one carrier per domain capability record

A valid implementation can use either:

- `buddy:{profile_id}:{domain_id}`
- another stable domain-owned carrier id

The exact string format is not the contract.

The contract is:

- no two unrelated domains share the same execution carrier
- capability growth reads only from the carrier bound to the active domain capability record
- archived carrier facts never bleed into a fresh domain's capability score

---

## 8. Service Changes

### 8.1 `BuddyOnboardingService`

`confirm_primary_direction(...)` must no longer think only in terms of:

- update `GrowthTarget`
- swap `BuddyDomainCapabilityRecord`

It must also decide the domain carrier transition:

- keep current carrier
- restore archived carrier
- create fresh carrier

### 8.2 Domain expansion write path

Chat-side domain expansion must update the active domain's scope without changing carrier ownership.

This should be a separate write path from hard switching.

It must not call the hard-switch preview/confirm flow.

### 8.3 `BuddyDomainCapabilityGrowthService`

Growth refresh must stop discovering runtime truth by:

- `profile_id -> buddy:{profile_id}`

It must instead read:

- `active domain capability -> bound carrier -> canonical runtime facts`

This is the critical fix for the current leakage bug.

### 8.4 Projection services

`BuddyProjectionService`, `/buddy/surface`, and Runtime Center buddy summary must continue reading:

- the active `BuddyDomainCapabilityRecord`

But that active record must now reflect a domain-owned carrier chain rather than a global carrier chain.

---

## 9. Frontend Behavior

### 9.1 Stage display

Stage remains capability-stage, not relationship-stage, and still uses:

- `幼年期`
- `成长期`
- `成熟期`
- `完全体`
- `究极体`

### 9.2 Switching UI

The page switch UI is only for hard switching:

- continue current domain
- restore archived domain
- start new domain

It should not be reframed as the general place to broaden the current domain.

### 9.3 Chat continuity

When restoring an archived domain:

- chat should return to that domain's original thread/continuity chain

When expanding the current domain in chat:

- chat stays in the current thread

---

## 10. Non-Goals

This spec does not:

- redesign Buddy relationship signals
- rename internal stage enums
- redesign the whole chat UI
- delete archived domain history
- create a second runtime truth source outside the existing industry/runtime chain

---

## 11. Acceptance Criteria

This work is complete when:

1. cross-domain `start-new` creates a new capability record **and** a new isolated execution carrier
2. archived domain carriers are preserved and restorable
3. restore returns to the original domain carrier and original continuity chain
4. active capability growth reads only the active domain's carrier facts
5. chat can widen the active domain without forcing a hard switch
6. chat may recommend page switching when drift becomes cross-domain, but never auto-switches domains
7. Chat / BuddyPanel / Runtime Center all show stage derived from the active domain-owned carrier chain with no cross-domain leakage
