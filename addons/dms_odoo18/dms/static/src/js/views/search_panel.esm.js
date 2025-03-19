/** @odoo-module **/
/* Copyright 2021-2024 Tecnativa - Víctor Martínez
 * Copyright 2024 Subteno - Timothée Vannier (https://www.subteno.com).
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */

 import { SearchPanel } from "@web/search/search_panel/search_panel";
 import { registry } from "@web/core/registry";
 import { useState } from "@web/core/utils/hooks"; // For state management in Odoo components

 class DMSSearchPanel extends SearchPanel {
    constructor() {
        super(...arguments);
        this.state = useState({ searchTerm: "" }); // Initialize the state
    }

    _getCategoryDomain(excludedCategoryId) {
        const domain = super._getCategoryDomain(...arguments);
        // Example: Update the search term when you need
        if (this.state.searchTerm) {
            // You can apply the search term to the domain here if needed
        }
        return domain;
    }

    // You can create a method to update the state
    _onSearchTermChange(newTerm) {
        this.state.searchTerm = newTerm;
    }
 }

 // Register the search view with the appropriate category and component
 registry.category("views").add("dms_search_panel", {
    type: "search",
    component: DMSSearchPanel,
    Controller: DMSSearchPanel,
 });
