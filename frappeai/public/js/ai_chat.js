/* SmartOps AI Chat - Main Page Script */

frappe.pages["ai-chat"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper,
        title: "SmartOps AI Assistant",
        single_column: true,
    });

    const page = wrapper.page;
    page.set_indicator("AI Ready", "green");

    // Context selector
    const context_options = [
        { label: "General", value: "general" },
        { label: "Financial", value: "financial" },
        { label: "Sales", value: "sales" },
        { label: "HR", value: "hr" },
    ];

    let current_context = "general";
    let session_id = null;
    let is_loading = false;

    const context_select = page.add_field({
        fieldname: "context",
        fieldtype: "Select",
        label: "Context",
        options: context_options.map(o => o.value).join("\n"),
        default: "general",
        change() {
            current_context = this.value;
        }
    });

    page.add_action_item("New Chat", () => {
        session_id = null;
        render_messages([]);
        frappe.show_alert({ message: "New chat started", indicator: "green" });
    });

    page.add_action_item("Chat History", () => {
        show_history_dialog();
    });

    // Render main chat UI
    const $body = $(wrapper).find(".page-content");
    $body.html(`
        <div class="smartops-chat-wrapper" style="
            display: flex;
            flex-direction: column;
            height: calc(100vh - 140px);
            max-width: 860px;
            margin: 0 auto;
            padding: 0 16px;
        ">
            <div class="smartops-messages" id="smartops-messages" style="
                flex: 1;
                overflow-y: auto;
                padding: 24px 0 16px;
                display: flex;
                flex-direction: column;
                gap: 16px;
            ">
                <div class="smartops-welcome" style="
                    text-align: center;
                    padding: 40px 20px;
                    color: var(--text-muted);
                ">
                    <div style="font-size: 48px; margin-bottom: 12px;">🤖</div>
                    <h3 style="font-weight: 500; color: var(--heading-color);">SmartOps AI Assistant</h3>
                    <p style="margin: 8px 0 24px;">Ask me anything about your business data.</p>
                    <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                        ${get_suggestion_chips()}
                    </div>
                </div>
            </div>
            <div class="smartops-input-area" style="
                padding: 16px 0 24px;
                border-top: 1px solid var(--border-color);
            ">
                <div style="display: flex; gap: 10px; align-items: flex-end;">
                    <textarea
                        id="smartops-input"
                        placeholder="Ask about your business... (Press Enter to send, Shift+Enter for new line)"
                        style="
                            flex: 1;
                            border: 1px solid var(--border-color);
                            border-radius: 8px;
                            padding: 10px 14px;
                            font-size: 14px;
                            resize: none;
                            min-height: 44px;
                            max-height: 120px;
                            font-family: var(--font-stack);
                            line-height: 1.5;
                            background: var(--fg-color);
                            color: var(--text-color);
                        "
                        rows="1"
                    ></textarea>
                    <button id="smartops-send-btn" class="btn btn-primary" style="
                        height: 44px;
                        min-width: 80px;
                        border-radius: 8px;
                        font-size: 14px;
                    ">Send</button>
                </div>
                <p style="font-size: 11px; color: var(--text-muted); margin: 6px 0 0; text-align: center;">
                    AI responses are based on your live ERPNext data. Always verify important decisions.
                </p>
            </div>
        </div>
    `);

    // Auto-resize textarea
    const $textarea = $("#smartops-input");
    $textarea.on("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
    });

    // Send on Enter (not Shift+Enter)
    $textarea.on("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send_message();
        }
    });

    $("#smartops-send-btn").on("click", send_message);

    // Suggestion chips
    $(document).on("click", ".smartops-chip", function () {
        const text = $(this).text();
        $textarea.val(text);
        send_message();
    });

    function get_suggestion_chips() {
        const suggestions = [
            "What are my outstanding invoices?",
            "How is business this month?",
            "Which customers owe me the most?",
            "Show me this week's sales summary",
        ];
        return suggestions.map(s =>
            `<span class="smartops-chip" style="
                background: var(--control-bg);
                border: 1px solid var(--border-color);
                border-radius: 20px;
                padding: 6px 14px;
                font-size: 13px;
                cursor: pointer;
                color: var(--text-color);
            ">${s}</span>`
        ).join("");
    }

    function send_message() {
        if (is_loading) return;
        const message = $textarea.val().trim();
        if (!message) return;

        // Add user message to UI
        append_message("user", message);
        $textarea.val("").css("height", "auto");

        // Show loading
        const loading_id = "loading-" + Date.now();
        append_loading(loading_id);
        is_loading = true;
        $("#smartops-send-btn").prop("disabled", true).text("...");

        // Remove welcome screen
        $(".smartops-welcome").remove();

        // Call API
        frappe.call({
            method: "frappeai.frappe_ai.api.chat.ask_ai",
            args: {
                message: message,
                session_id: session_id,
                context_type: current_context,
            },
            callback(r) {
                is_loading = false;
                $("#smartops-send-btn").prop("disabled", false).text("Send");
                $(`#${loading_id}`).remove();

                if (r.message) {
                    session_id = r.message.session_id;
                    append_message("assistant", r.message.reply);
                }
            },
            error(e) {
                is_loading = false;
                $("#smartops-send-btn").prop("disabled", false).text("Send");
                $(`#${loading_id}`).remove();
                append_message("assistant", "Sorry, I encountered an error. Please check your SmartOps Settings and API key.");
            }
        });
    }

    function append_message(role, content) {
        const is_user = role === "user";
        const formatted = format_message(content);

        const $msg = $(`
            <div class="smartops-msg smartops-msg-${role}" style="
                display: flex;
                gap: 10px;
                align-items: flex-start;
                ${is_user ? "flex-direction: row-reverse;" : ""}
            ">
                <div class="smartops-avatar" style="
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    background: ${is_user ? "var(--primary)" : "#6c5ce7"};
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 14px;
                    flex-shrink: 0;
                    color: white;
                ">${is_user ? "👤" : "🤖"}</div>
                <div class="smartops-bubble" style="
                    max-width: 75%;
                    background: ${is_user ? "var(--primary)" : "var(--fg-color)"};
                    color: ${is_user ? "white" : "var(--text-color)"};
                    border: ${is_user ? "none" : "1px solid var(--border-color)"};
                    border-radius: ${is_user ? "16px 4px 16px 16px" : "4px 16px 16px 16px"};
                    padding: 10px 14px;
                    font-size: 14px;
                    line-height: 1.6;
                ">${formatted}</div>
            </div>
        `);

        $("#smartops-messages").append($msg);
        scroll_to_bottom();
    }

    function append_loading(id) {
        const $loading = $(`
            <div id="${id}" class="smartops-msg smartops-msg-assistant" style="
                display: flex; gap: 10px; align-items: flex-start;
            ">
                <div style="
                    width: 32px; height: 32px; border-radius: 50%;
                    background: #6c5ce7; display: flex; align-items: center;
                    justify-content: center; font-size: 14px; color: white;
                ">🤖</div>
                <div style="
                    background: var(--fg-color); border: 1px solid var(--border-color);
                    border-radius: 4px 16px 16px 16px; padding: 12px 16px;
                ">
                    <span style="color: var(--text-muted);">Thinking</span>
                    <span class="smartops-dots" style="color: var(--primary);">...</span>
                </div>
            </div>
        `);
        $("#smartops-messages").append($loading);
        scroll_to_bottom();

        // Animate dots
        let dots = 0;
        const interval = setInterval(() => {
            if (!$(`#${id}`).length) { clearInterval(interval); return; }
            dots = (dots + 1) % 4;
            $(`#${id} .smartops-dots`).text(".".repeat(dots + 1));
        }, 400);
    }

    function format_message(text) {
        // Basic markdown-like formatting
        return text
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/`(.*?)`/g, "<code style='background:var(--control-bg);padding:1px 4px;border-radius:3px;font-size:12px;'>$1</code>")
            .replace(/\n/g, "<br>");
    }

    function scroll_to_bottom() {
        const $messages = $("#smartops-messages");
        $messages.scrollTop($messages[0].scrollHeight);
    }

    function show_history_dialog() {
        frappe.call({
            method: "smartops.api.chat.get_sessions",
            callback(r) {
                if (!r.message || !r.message.length) {
                    frappe.msgprint("No chat history yet.");
                    return;
                }

                const rows = r.message.map(s =>
                    `<tr style="cursor:pointer;" data-id="${s.name}">
                        <td style="padding:8px 12px;">${s.session_title}</td>
                        <td style="padding:8px 12px;color:var(--text-muted);font-size:12px;">${frappe.datetime.prettyDate(s.modified)}</td>
                    </tr>`
                ).join("");

                const d = new frappe.ui.Dialog({
                    title: "Chat History",
                    fields: [],
                });
                d.body.innerHTML = `
                    <table style="width:100%;border-collapse:collapse;">
                        <thead><tr style="border-bottom:1px solid var(--border-color);">
                            <th style="padding:8px 12px;text-align:left;font-weight:500;">Session</th>
                            <th style="padding:8px 12px;text-align:left;font-weight:500;">Date</th>
                        </tr></thead>
                        <tbody>${rows}</tbody>
                    </table>`;

                $(d.body).find("tr[data-id]").on("click", function () {
                    const id = $(this).data("id");
                    session_id = id;
                    frappe.call({
                        method: "smartops.api.chat.get_session_messages",
                        args: { session_id: id },
                        callback(r) {
                            if (r.message) {
                                render_messages(r.message);
                                d.hide();
                            }
                        }
                    });
                });

                d.show();
            }
        });
    }

    function render_messages(messages) {
        const $msgs = $("#smartops-messages");
        $msgs.empty();

        if (!messages.length) {
            $msgs.html(`<div class="smartops-welcome" style="text-align:center;padding:40px 20px;color:var(--text-muted);">
                <div style="font-size:48px;margin-bottom:12px;">🤖</div>
                <h3 style="font-weight:500;color:var(--heading-color);">SmartOps AI Assistant</h3>
                <p style="margin:8px 0 24px;">Ask me anything about your business data.</p>
                <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">${get_suggestion_chips()}</div>
            </div>`);
            return;
        }

        messages.forEach(msg => append_message(msg.role, msg.content));
    }
};
