"""Individually authored employee requests for FactoryBench-100.

These are intentionally business-facing.  They state the uncertainty and the
decision an employee needs, but never disclose source locations, tool names,
record lookup order, verifier fields, or the private solution path.
"""

from __future__ import annotations


HUMAN_REQUESTS: dict[str, str] = {
    "Commit one pallet of Luma lamps": (
        "Sales needs a date for one pallet of Luma lamps. When can we honestly have it finished with today's schedule and stock, what is preventing an earlier run, and do expediting parts or adding a shift change the answer? Commit the best approved plan and prepare the launch-team update for review."
    ),
    "Split a defense order around an export hold": (
        "Trade compliance says part of the defense order may be clear to proceed while the export line is still on hold. Tell the account team what we can commit now, what must wait, and whether splitting the order is better than holding everything. Put only the cleared demand into motion."
    ),
    "Recover a customer promise after a carrier rollover": (
        "Our carrier rolled the sailing behind a customer promise and sales needs a credible recovery date today. Work out the earliest arrival we can stand behind, whether a mixed air-and-ocean move is worth the premium, and what quantity each choice protects. Update the production commitment behind the chosen plan."
    ),
    "Replace an obsolete configuration before fulfillment": (
        "The controller configuration on an open customer order is obsolete, but several similar replacement records are circulating. Determine which open units are genuinely covered by the released change, explain what cannot be touched, and decide whether substitution, waiting for the old part, or asking the customer for a deviation is the safest path. Apply the authorized choice."
    ),
    "Stop supply for a duplicated customer release": (
        "A new EDI release appears to duplicate demand we already accepted, and the supplier cancellation window is closing. Establish whether it is truly a duplicate, how much associated supply can still be stopped without hurting legitimate demand, and the consequence of leaving both releases open. Cancel only the unsupported commitment and brief the account team."
    ),
    "Release the flight-test controller build": (
        "The flight-test team wants its controller build released, but the floor is not convinced every gate is ready. Give the cell lead a yes-or-no release decision, the quantity and completion we can support, and the best fallback if only part of the build is ready. Create the order only for the approved plan."
    ),
    "Resequence burn-in ahead of final assembly": (
        "Final assembly is about to wait on burn-in, and moving the step may recover the build. Find the earliest sequence that respects work already completed and protected chamber time, compare it with waiting or using the contract chamber, and tell the cell lead what each choice does to completion. Put the approved sequence on the order."
    ),
    "Insert an approved rework operation": (
        "Quality has issued a disposition for failed units on the active order, but we must not rework units already accepted or scrapped. Decide exactly which material the disposition covers, whether rework is preferable to scrap or a use-as-is request, and when the work can finish. Add the rework step only if the released disposition supports it."
    ),
    "Replace a constrained relay on an active order": (
        "The original relay will miss the install window and engineering says a substitute may be available. Work out how much remaining demand the substitute can legally cover, what stock or orders fall outside its effectivity, and whether using it beats waiting or reducing the build. Change only the supported material requirement."
    ),
    "Assign certified contract labor to wiring": (
        "Wiring is short of labor for the current build and an agency has offered a contractor. Tell the cell lead whether that person is qualified and actually free for the needed hours, when the operation would finish with each credible staffing choice, and whether the rate is within authority. Add only the approved resource assignment."
    ),
    "Issue the earliest-expiry conforming adhesive": (
        "The shift needs adhesive for operation 10 and wants to consume the oldest usable lot first. Determine the quantity we can issue without touching expired, reserved, or uncertified stock, explain whether a later-expiry lot or waiver would improve the outcome, and post the lot movement the evidence supports."
    ),
    "Return unused copper from a canceled operation": (
        "Operation 20 was canceled and there is copper left at the work center. Establish how much was genuinely issued, consumed, scrapped, and still physically present, then decide what can return to stores without losing its project ownership. Post the bounded return and leave the shift with the discrepancy, if any."
    ),
    "Correct a wrong-lot scan before consumption": (
        "A material handler believes the wrong copper lot was scanned into an operation that has not consumed it yet. Identify the actual movement, make sure a similar scan is not being mistaken for this one, and decide whether it can be safely reversed and reposted now or must wait for review. Correct the traceable record only."
    ),
    "Report serial-controlled panel completion": (
        "The final-operation quantity does not agree with the panel serial records. Tell the shift which serials are truly complete, which ones still have a test or traveler problem, and the operational effect of holding the exceptions instead of completing the header quantity. Post completion only for the defensible serial set."
    ),
    "Post calibrated test-bench labor actuals": (
        "Test-bench time is missing from the active order, but some submitted hours may be duplicated or outside the calibration window. Determine the actual hours that belong to this operation, the consequence of holding the questionable entries, and the amount we can post now. Record only the supported resource usage."
    ),
    "Reroute assembly after a spindle failure": (
        "The primary assembly cell is down after a spindle failure and the customer order is exposed. Find the earliest qualified recovery plan that does not displace protected work, compare it with waiting for repair and adding an extra shift, and show operations the cost and completion impact. Reroute the operation if the best choice is already approved."
    ),
    "Recover output after a certified welder absence": (
        "A certified welder is unexpectedly out and the backlog is growing. Work out which qualified replacement capacity is truly available, when output recovers under waiting, agency cover, or overtime, and what risk each choice carries. Put the authorized recovery on the schedule without assigning unqualified labor."
    ),
    "Move outsourced coating around a supplier outage": (
        "Our coating supplier has shut down with work due back before assembly. Decide whether the approved alternate can take the right quantity and process in time, what remains stranded at the incumbent, and how rerouting compares with waiting. Move only the eligible outside operation and give production a defensible new date."
    ),
    "Apply approved weekend overtime to backlog": (
        "Operations has weekend-overtime approval for part of the backlog, but not every open order belongs in that scope. Determine which work actually benefits, whether qualified inspection and work-center coverage are available, and how the approved weekend changes completion versus the weekday plan. Schedule only the authorized recovery."
    ),
    "Hold production for an expired torque-tool calibration": (
        "We discovered that a torque tool expired while serial-controlled work was in process. Establish which units are exposed and which were completed under a valid calibration, then advise whether replacement tooling or recalibration is the fastest safe recovery. Open the necessary corrective work and keep only the affected production held."
    ),
    "Open repair for a failed servo drive": (
        "A servo drive has failed and production needs a return-to-service date, not just a repair ticket. Compare an internal repair, an OEM exchange, and running to the next shutdown using the actual fault, parts, and qualified labor situation. Open the approved repair with the scope and date the evidence supports."
    ),
    "Extend a pump repair after teardown findings": (
        "The pump teardown found more damage than we expected, and operations needs it for next week's run. When can we credibly return it to service, what is actually holding that date, and would expediting the part or moving the repair help enough to justify it? If the approved scope covers the best plan, update the commitment and let operations know."
    ),
    "Move a repair to the qualified electrical shop": (
        "The current shop cannot finish the electrical portion of this repair, while another internal shop and a contractor both claim availability. Determine which destination is actually qualified and free, what each option does to return-to-service, and whether moving the work is within authority. Reroute the operation to the best approved shop."
    ),
    "Attach the vendor diagnostic report to maintenance": (
        "The vendor sent several similarly named diagnostic reports and the maintenance team needs the one that governs this asset failure. Identify the report that truly belongs to the open order, explain why the other candidates are unsafe to use, and decide whether we can proceed or need a new report. Link only the verified reference."
    ),
    "Convert a repeated bearing alarm into planned work": (
        "Reliability wants to know whether the repeated bearing alarm has crossed the threshold for planned maintenance or is still noise. Determine what events genuinely count, when the work can be done without disrupting protected production, and how a recurring program compares with one-time repair or continued monitoring. Record the approved decision."
    ),
    "Advance lubrication after a meter spike": (
        "A meter spike may have pulled the next lubrication forward, but the history also contains resets and duplicate readings. Tell reliability whether the asset is truly due, the first safe service window, and the risk of keeping the calendar date versus advancing it. Update only the bounded program window that is authorized."
    ),
    "Generate the quarterly compressor forecast": (
        "Reliability is preparing the quarterly compressor plan and wants a clean forecast rather than every row in the asset roster. Determine which active compressors are genuinely due, which rows are duplicates or fall in blackout periods, and whether the available shutdown capacity can absorb them. Generate only the supported forecast horizon."
    ),
    "Create due work for guarded saw inspections": (
        "The next shutdown is approaching and we need to know which guarded-saw inspections should become work orders now. Separate genuinely due assets from work already generated, inactive equipment, and blackout conflicts, then compare doing the due set now with deferring it. Create only the approved due work."
    ),
    "Create a contamination-control program": (
        "Quality has approved a new contamination-control standard, but it does not apply to every asset in the plant. Define the active food-contact equipment that really belongs in the program, the first workable cleaning windows, and the consequence of copying the generic program or including everything. Create the scoped program if coverage and approval are sufficient."
    ),
    "Link the revised lockout procedure to PM work": (
        "A PM order is waiting for the correct lockout procedure and Drive contains drafts, superseded copies, and another asset's revision. Decide which released procedure applies on the work date, whether the job can start as planned, and what happens if no valid revision is available. Link only the procedure that passes that test."
    ),
    "Award the enclosure tooling package": (
        "We need to award the enclosure tooling package without mistaking the lowest sticker price for the best bid. Compare the technically acceptable offers on landed cost, lead time, capacity, and commercial exceptions, show whether the launch date and sourcing authority are protected, and identify the strongest fallback. Create the draft award only for the supported choice."
    ),
    "Record the supplier's expedited promise": (
        "The supplier says it can expedite our open order, but its acknowledgment may not cover every line or unit. Determine exactly what promise can be relied on, how it changes the downstream production date, and whether accepting it is better than keeping the current schedule. Record only the supplier-confirmed commitment."
    ),
    "Cancel a resin order after a safety bulletin": (
        "A safety bulletin names resin we still have on order, and the supplier cutoff is close. Establish which open quantity is actually affected and still cancelable, what has already been received or consumed, and whether replacement coverage makes cancellation safe. Stop only the covered purchase commitment."
    ),
    "Close a fully received calibration-services PO": (
        "The calibration-services PO looks complete, but the close must not hide an unaccepted service or unmatched invoice. Determine whether every dollar is received, accepted, invoiced, and approved, explain the remaining exposure if any, and decide whether closing now or leaving it open is correct. Apply the supported close action."
    ),
    "Create emergency supply for a line-down shortage": (
        "The line is down for a component shortage and planners need to know what supply action actually restores it. Calculate the uncovered need and the first usable arrival, compare emergency buying with transfer or waiting for firm inbound, and show which option protects the next production window. Create supply only for the net gap."
    ),
    "Receive a lot-controlled relay shipment": (
        "A relay shipment is at the dock, but the packing slip, PO, certificate, and physical count do not obviously agree. Decide what quantity and lot can enter receiving today, what must remain outside the receipt, and the production impact of holding the discrepancy. Create only the supported receipt request."
    ),
    "Reject water-damaged enclosures at inspection": (
        "Several enclosures arrived with visible water damage while the rest of the shipment may be usable. Determine the accepted and rejected quantities, how a partial receipt affects the build, and whether replacement timing changes the preferred disposition. Record the return for only the units that fail inspection."
    ),
    "Correct a transposed receiving quantity": (
        "The receipt interface appears to contain a transposed quantity that would overstate inventory. Establish the actual dock quantity, the amount of the error, and whether correcting now creates any PO or inspection exception. Fix the one receipt line and give receiving the resulting usable quantity."
    ),
    "Deliver inspected copper to project stores": (
        "Copper for a project order has passed receiving, but not all of the header quantity is eligible for project stores. Work out the quantity that preserves the right project, task, lot, and acceptance status, explain the consequence of holding the balance, and post only the supported delivery."
    ),
    "Return mislabeled relays to the supplier": (
        "Receiving found relays with supplier labels that do not match the ordered item. Determine which units are covered by the return authorization, whether any correctly labeled stock can still support production, and how replacement lead time affects the decision. Return only the confirmed mislabeled quantity."
    ),
    "Validate a clean three-way-matched invoice": (
        "Accounts Payable believes this invoice is clean, but it must be proven against what was ordered, received, and accepted. Establish the supported amount and any residual variance, then say whether validation now is safer than holding for correction. Validate only if the document is genuinely within tolerance."
    ),
    "Place a freight-variance hold": (
        "A supplier invoice includes freight that may not be allowed by the purchase terms. Determine the supported invoice value, the exact freight exposure, and whether it exceeds the applicable tolerance or has separate approval. Place the narrow hold needed to protect payment without blocking unrelated documents."
    ),
    "Release a hold after the supplier credit arrives": (
        "The supplier says its credit resolves the variance behind an existing invoice hold. Confirm whether the credit fully matches that exposure, identify any residual amount or timing issue, and decide whether the hold can be released now. Record the release only if the invoice is clean after the credit."
    ),
    "Correct payment terms from the signed contract": (
        "The invoice shows different payment terms from the signed supplier agreement. Determine which terms govern this supplier site and invoice date, quantify the cash-timing difference, and make sure the apparent newer record is not a draft or unrelated amendment. Correct only this invoice if the contract supports it."
    ),
    "Enter a non-PO metrology invoice": (
        "Metrology submitted an invoice without a purchase order and needs a payment decision before the close. Determine whether the service, coding, approval, supplier site, and amount support a legitimate non-PO entry, and identify the safest fallback if they do not. Enter only the approved invoice rather than inventing purchasing support."
    ),
    "Approve a conditional alternate for molded parts": (
        "The incumbent molded-parts source is constrained and procurement wants to use an alternate under conditions. Decide whether the alternate has cleared the necessary risk and quality evidence, how much demand the trial approval can cover, and what remains exposed if it is not used. Create only the supply allowed by the conditional approval."
    ),
    "Escalate sole-source spend concentration": (
        "Our open commitments to one supplier may have crossed the concentration threshold. Establish the real exposure after exclusions, compare the approved mitigation with doing nothing or moving spend immediately, and explain the operational consequence of each. Record the supplier acknowledgment that is actually supported and escalate the remaining risk."
    ),
    "Suspend orders after a sanctions-screening hit": (
        "A sanctions alert may match one of our suppliers, but a similar-name false positive would be costly. Determine whether the hit belongs to the supplier on the open order, what commitments are still stoppable, and how continuity can be protected. Suspend only the purchase document covered by legal direction."
    ),
    "Close a supplier remediation purchase order": (
        "The supplier says every remediation deliverable is complete and wants its PO closed. Verify whether all required work was accepted and financially settled, identify any unresolved obligation, and compare closing now with keeping the document open. Finally close it only if no exposure remains."
    ),
    "Open maintenance after vendor-caused equipment damage": (
        "A supplier incident damaged plant equipment and operations needs a repair plan plus a defensible vendor record. Determine the affected asset and supported damage scope, the earliest credible recovery, and whether internal repair or vendor recovery is better. Open the bounded maintenance work and preserve the supplier impact."
    ),
    "Create incoming inspection for plated busbars": (
        "Plated busbars have arrived and quality must decide what inspection applies before production can use them. Identify the current plan for this supplier, item, and lot, tell the floor what quantity can be tested now and when a result is possible, and create the inspection record only for the supported receipt."
    ),
    "Record failed dielectric-test samples": (
        "The dielectric lab reports failed samples, but the inspection header does not yet reflect them. Determine which sample results belong to this lot and plan, the accepted and rejected quantities, and what downstream material must be held. Record the defensible result without overwriting another inspection."
    ),
    "Correct a mistyped dimensional result": (
        "A technician says one dimensional result was mistyped and the current disposition may be wrong. Establish the actual measurement and the inspection record it belongs to, decide whether the correction changes acceptance, and explain what material remains affected. Update only the erroneous result."
    ),
    "Quarantine an expired chemical lot": (
        "A chemical lot appears to have expired while some quantity remains on hand. Determine the affected quantity and locations, whether any material was consumed before expiry, and how quarantine compares with a documented extension or replacement. Move only the expired stock out of available inventory."
    ),
    "Create rework supply from a failed final inspection": (
        "Final inspection failed part of a build and the cell wants replacement supply. Work out the quantity that truly needs rework after accepted, scrapped, and duplicate records are removed, when the rework can finish, and whether a new build or repair is preferable. Create supply only for the approved rework scope."
    ),
    "Transfer a constrained relay lot between plants": (
        "One plant is short of relays while another may have a usable lot, but protected allocations cannot be disturbed. Determine the net transferable quantity, the first arrival at the receiving plant, and whether transfer is better than buying or waiting. Post the approved movement with its lot and destination intact."
    ),
    "Post a blind cycle-count adjustment": (
        "Two independent counts disagree with the system balance for a controlled item. Establish the best supported on-hand quantity, the adjustment and uncertainty behind it, and whether another recount would materially change the answer. Post only the bounded correction approved by inventory control."
    ),
    "Move suspect housings into quarantine": (
        "A supplier alert may affect several housing lots in stores. Trace the alert to the quantities still on hand, separate unaffected or already consumed material, and tell production what coverage remains after containment. Move only the suspect stock into quarantine."
    ),
    "Return excess project copper to common stock": (
        "A completed project has copper left over and another program could use it. Determine what quantity is truly excess, whether finance has released its ownership, and the impact of transferring it versus leaving it with the project. Move only the approved residual quantity to common stores."
    ),
    "Create supply for an approved kanban breach": (
        "The physical count is below the kanban minimum, but an open replenishment may already cover part of the gap. Determine the true shortage, when existing and new supply would arrive, and whether expediting is justified. Create only the additional replenishment the approved exception requires."
    ),
    "Cover an unplanned copper demand spike": (
        "Demand for copper jumped after the latest plan and production wants a coverage date. Net the new requirement against usable stock and firm inbound, compare buy, transfer, and schedule alternatives, and identify the constraint behind the earliest feasible plan. Create supply only for the remaining gap."
    ),
    "Pull in supply after a forecast-consumption jump": (
        "Actual orders consumed the forecast faster than expected and the current supply date may now be too late. Determine the uncovered demand and first date the supplier and production calendar can jointly support, then compare pulling in, splitting, or accepting the delay. Revise only the approved production commitment."
    ),
    "Cancel redundant purchase supply after demand deletion": (
        "The demand behind an open purchase order was deleted, but part of that supply may have been re-pegged or received. Establish what is truly redundant and still cancelable, the risk of canceling too much, and whether leaving it open has a better use. Stop only the unsupported supply."
    ),
    "Replace a constrained component in planned work": (
        "Planning cannot cover the original component for an upcoming order and an approved substitute may bridge the gap. Determine the demand inside the substitute's effectivity, available converted quantity, and completion under substitute, wait, or reduced build. Change only the eligible planned material."
    ),
    "Create constrained supply for a service allocation": (
        "A priority service request needs constrained material that is also wanted by regular production. Determine what the approved allocation actually reserves, the uncovered service need and delivery date, and the customer impact of each feasible source. Create only the service-scoped supply decision."
    ),
    "Implement a released relay substitution": (
        "Engineering released a relay substitution, but only some open work may be inside its revision and serial effectivity. Identify the orders and quantity that can change now, what must remain on the old design, and whether rework or deferment is the better fallback. Implement only the authorized material change."
    ),
    "Move inspection to the revised routing step": (
        "The released router moves inspection to a different step, while the active order still carries the old sequence. Determine what open work is eligible for the change, whether the new work center has a safe slot, and the impact of moving now versus deferring. Update the supported operation only."
    ),
    "Add new test-fixture capacity to an active order": (
        "A newly qualified fixture may relieve the test bottleneck on an active order. Establish whether its approval covers this product and operation, how much usable capacity it really adds, and whether the completion gain justifies assigning it. Add the resource only within the released change scope."
    ),
    "Attach the released service bulletin to repair work": (
        "A repair order needs the governing service bulletin, but several revisions and model ranges are available. Determine which released bulletin applies to this asset and work date, what happens if the wrong one is used, and whether the repair can proceed. Attach only the verified technical reference."
    ),
    "Create a pilot work order for the revised design": (
        "Engineering wants a pilot build of the revised design before broader release. Determine the quantity, revision, isolated material, fixture coverage, and first slot the approval can support, then compare that plan with waiting or reducing scope. Create only the approved pilot order."
    ),
    "Post missing setup labor from signed timecards": (
        "Setup labor is missing from WIP cost, but the timecard batch contains duplicates and unsupported hours. Determine the hours and rate that genuinely belong to this operation and period, quantify the correction, and explain the residual exception. Post only the supported labor actual."
    ),
    "Reverse a duplicated copper issue": (
        "WIP appears to include the same copper issue twice. Prove whether the second posting is a true duplicate, reconcile the physical quantity and cost still on hand, and show the period impact of reversing it versus leaving it. Post only the return needed to restore the correct WIP balance."
    ),
    "Record scrap discovered during final count": (
        "The final physical count found fewer good units than the operation history reports. Determine the completed, rejected, missing, and scrapped quantities that make the order reconcile, explain the cost and output impact, and decide whether the loss belongs in this period. Post only the supported scrap transaction."
    ),
    "Validate an outside-processing invoice": (
        "An outside processor invoiced the order and the controller needs to know what is payable now. Tie the billed quantity and rate to accepted supplier output, quantify any rejected, missing, duplicate, or rate-variance exposure, and compare validation with a hold or correction. Validate only the supported invoice."
    ),
    "Reschedule incomplete WIP out of the close window": (
        "Period close is approaching and this order is physically unfinished despite an in-period completion date. Establish what work is actually complete, the first qualified next-period slot, and the customer and accounting effect of moving it. Revise the dates without falsely completing or reversing valid current-period activity."
    ),
    "Move project-owned relays to the build subinventory": (
        "A project build needs relays that are available elsewhere, but ownership and reservations must survive the move. Determine the quantity carrying the right project, task, lot, and approval, what must stay put, and whether transfer meets the build date. Post only the eligible project movement."
    ),
    "Create project supply for a customer milestone": (
        "The project milestone is at risk and the team wants dedicated supply. Calculate the net project need after eligible coverage, identify the first date procurement and prototype capacity can support, and compare that plan with using common stock or moving the milestone. Create only the approved project-scoped supply."
    ),
    "Align an order to the corrected project task": (
        "Finance says an open manufacturing order was linked to the wrong project task. Determine the single correct attribution and its effective date, what similar task records must not be used, and the schedule or billing consequence of the correction. Update only the open order covered by the approval."
    ),
    "Return unused project material from WIP": (
        "A canceled project operation still holds material that may be reusable. Establish what was issued, consumed, scrapped, and physically left, then decide how much can return without crossing project ownership or lot controls. Post the supported return and preserve any unresolved discrepancy."
    ),
    "Create a project-specific prototype order": (
        "The signed project scope calls for a prototype, but the team needs a realistic quantity and finish date before committing. Determine what the released design, funding, material, and isolated capacity support, compare the useful alternatives, and create only the project order authorized by that conclusion."
    ),
    "Replenish a technician's critical relay stock": (
        "A field technician is below minimum on a critical relay while regional supply is constrained. Determine the entitled replenishment after open demand and protected allocations, the earliest arrival, and whether transfer, purchase, or waiting is best for service continuity. Create only the approved technician-stock supply."
    ),
    "Quarantine a returned field controller": (
        "A returned controller has reached the depot and may be mixed with an advance-replacement unit and accessories. Identify the serial and quantity that truly belong to the RMA, explain what must remain outside the movement, and decide the safest disposition. Move only the confirmed customer return into quarantine."
    ),
    "Open depot repair for a customer asset": (
        "A customer asset has arrived at the depot and service needs a credible repair commitment. Verify the covered failure and entitlement, compare internal repair, exchange, and delayed repair using real bench and part availability, and give the customer the earliest defensible date. Open only the authorized repair scope."
    ),
    "Issue a reserved spare to an emergency repair": (
        "An emergency repair is waiting for a spare that may already be reserved for it. Determine the exact need and usable reserved lot, what stock belongs to other priorities, and whether issuing now protects the service date better than replenishing. Post only the supported material issue."
    ),
    "Receive an advance-replacement return": (
        "The customer returned equipment under an advance-replacement case, but the shipment contents and RMA record need to agree. Determine which serial and quantity we can receive, what is unrelated or missing, and how any discrepancy affects closure. Create the receipt only for the verified return."
    ),
    "Contain relays named in a supplier recall": (
        "A supplier recall names particular relay lots and production needs to know its real exposure. Trace what remains on hand, in work, or already consumed, separate stock outside the recall, and explain the coverage and schedule impact after containment. Move only the affected available quantity into quarantine."
    ),
    "Attach a certificate of conformance to repair work": (
        "A repair order needs a certificate of conformance before release, but several similar certificates are available. Determine which issuer, lot, item, asset, and validity period match the repair material, what the alternatives fail, and whether work can proceed. Attach only the immutable certificate that applies."
    ),
    "Hold payment for a missing conflict-minerals report": (
        "An invoice includes covered materials but the current conflict-minerals evidence may be incomplete. Determine the value exposed, what lines have valid reporting support, and whether a narrow hold, correction, or full payment is justified. Protect only the unsupported amount and keep unrelated invoices moving."
    ),
    "Create inspection for restricted-substance screening": (
        "A receipt requires restricted-substance screening before it can enter production. Identify the applicable current plan and affected lot, estimate when a defensible result is possible, and compare holding, screening, or rejecting the material. Create only the inspection supported by the compliance scope."
    ),
    "Open corrective maintenance after a safety interlock bypass": (
        "A safety interlock was bypassed and production is asking when the asset can run again. Establish the actual equipment exposure and repair scope, compare qualified internal and external recovery options, and identify the earliest safe return-to-service. Open the corrective work without releasing the asset beyond the safety approval."
    ),
    "Close a fully settled tooling PO before cutoff": (
        "A tooling PO is on the close exception list and appears financially settled. Determine whether every receipt, acceptance, invoice, payment, and remaining commitment truly nets to zero, explain any cutoff risk, and decide whether final close is appropriate. Close only this document if no exposure remains."
    ),
    "Validate the final matched invoice batch item": (
        "One invoice remains in the close batch and validation must not push an unsupported item into the period. Establish the matched amount, residual exception, accounting date, and cutoff impact, then compare validation with holding or correcting it. Validate only if the current period can properly absorb it."
    ),
    "Hold a duplicate invoice found in reconciliation": (
        "Reconciliation found an invoice that may duplicate one already recorded. Determine whether supplier, normalized number, date, amount, PO, and attachment evidence establish a true duplicate, distinguish any legitimate tax or credit difference, and quantify the payable amount. Place a hold only on the confirmed duplicate."
    ),
    "Move unfinished production beyond period end": (
        "An order still has unfinished production at cutoff even though its dates sit inside the closing period. Determine the real remaining work and first next-period slot, the cost and customer impact of moving it, and whether any current-period activity must stay untouched. Defer only the incomplete scope."
    ),
    "Post an omitted maintenance labor charge": (
        "A maintenance labor charge was omitted from the period, but the source hours and rate must be defensible. Determine what technician time belongs to the correct order and date, quantify any duplicate or unsupported amount, and decide whether the open period permits posting now. Record only the supported charge."
    ),
    "Acknowledge the anodizer's revised promise": (
        "The anodizer has sent a revised promise for outside processing and production needs to know whether to accept it. Match the commitment to the correct PO scope, determine the quantity and date we can rely on, and compare the resulting build impact with expediting or waiting. Record only the supplier-confirmed promise."
    ),
    "Receive accepted plated housings from processing": (
        "Plated housings are back from the supplier, but only accepted output should enter receiving. Determine the quantity supported by the shipment, outside-operation scope, lot, and inspection, explain the consequence of missing or rejected units, and create the receipt transaction for the defensible quantity."
    ),
    "Report outside operation completion after receipt": (
        "The supplier operation is ready to be reported complete, but the sent, returned, accepted, and rejected quantities do not all look alike. Establish the good quantity that can legitimately complete, what remains open, and how each choice affects the order. Post completion only for accepted returned output."
    ),
    "Record yield loss from rejected processed parts": (
        "The outside processor returned rejected parts and the order's yield no longer reconciles. Determine how sent quantity splits among accepted, rejected, and missing units, the production and cost impact, and whether any quantity still needs investigation. Record only the supported loss without counting it as good output."
    ),
    "Close an outside-processing PO after final acceptance": (
        "The outside-processing PO may be ready to close after final acceptance. Verify that ordered, sent, returned, accepted, invoiced, and paid quantities leave no open schedule or value, explain any residual risk, and compare final close with leaving the document open. Apply the supported close action only."
    ),
}


__all__ = ["HUMAN_REQUESTS"]
