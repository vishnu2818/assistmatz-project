/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

patch(FormRenderer.prototype, {
    async renderView() {
        const el = await this._super(...arguments);

        try {
            const record = this.state;
            const deadline = record.data.date_deadline;

            if (deadline) {
                const today = new Date().toISOString().slice(0, 10);

                if (deadline <= today) {
                    // Correct selector for Odoo 19 Date widget
                    const dateDiv = el.querySelector("div[name='date_deadline']");

                    if (dateDiv) {
                        dateDiv.style.color = "red";
                        dateDiv.style.fontWeight = "bold";
                    }
                }
            }
        } catch (err) {
            console.warn("Error applying red color:", err);
        }

        return el;
    },
});
// /** @odoo-module */


// import { Component, xml, onMounted } from "@odoo/owl";
// import { registry } from "@web/core/registry";

// class DeadlineDateTooltip extends Component {
//     setup() {
//         const raw = this.props.record.data.deadline_history || "[]";
    
//         const parsed = JSON.parse(raw);
//         this.tooltipText = parsed.length ? parsed.join(", ") : "No updates yet";

//         // After render: inject icon before label
//         onMounted(() => {
//             const label = document.querySelector("label[for='date_deadline_0']");
//             const input = document.querySelector("#date_deadline_0");
//             if (label && !label.previousElementSibling?.classList?.contains("deadline-tooltip-wrapper")) {
//                 const span = document.createElement("span");
//                 span.setAttribute("data-title", `Updated Dates: ${this.tooltipText}`);
//                 // span.textContent = "!";
//                 // span.style.cssText = `
//                 //     margin-right: 6px;
//                 //     color: black;
//                 //     border-radius: 6px;
//                 //     padding: 4px;
//                 //     cursor: pointer;
//                 // `;
//                 label.parentNode.insertBefore(span, label);
//             }
//              // Set input color to red if overdue
      
//             if (input && this.props.record.data.is_overdue) {
//                 input.style.background = "red";
//                 input.style.color = "white";
//                 input.style.width = "73px";
//             }
                
         
//         });
//     }
// }

// DeadlineDateTooltip.template = xml`<div/>`; // no need to render anything here

// registry.category("fields").add("deadline_date_tooltip", {
//     component: DeadlineDateTooltip,
// });

// import { registry } from "@web/core/registry";
// import { DateField } from "@web/views/fields/date/date_field";
// import { standardFieldProps } from "@web/views/fields/standard_field_props";

// export class DeadlineHighlightField extends DateField {
//     get classes() {
//         const baseClasses = super.classes || {};
//         const extraClasses = {};
//         const record = this.props.record?.data;

//         if (record?.date_deadline) {
//             const today = new Date();
//             today.setHours(0, 0, 0, 0);

//             const deadline = new Date(record.date_deadline);
//             deadline.setHours(0, 0, 0, 0);

//             if (deadline < today) {
//                 extraClasses["text-danger"] = true;
//                 extraClasses["fw-bold"] = true;
//             }
//         }

//         return { ...baseClasses, ...extraClasses };
//     }
// }

// DeadlineHighlightField.template = "DeadlineHighlightField";
// DeadlineHighlightField.props = standardFieldProps;

// registry.category("fields").add("deadline_highlight", DeadlineHighlightField);


