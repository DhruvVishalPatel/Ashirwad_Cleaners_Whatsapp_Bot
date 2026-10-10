import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import {
  MessageSquare,
  Send,
  PauseCircle,
  PlayCircle,
  Search,
  User,
  Phone,
  MapPin,
  Clock,
  Bot,
  UserCheck,
  RefreshCw,
  AlertCircle,
  ArrowLeft
} from 'lucide-react';

export default function ChatMessenger({ wsEvent }) {
  const [chats, setChats] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [loadingChats, setLoadingChats] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [togglingBot, setTogglingBot] = useState(false);
  const [chatError, setChatError] = useState(null);
  
  const [refreshing, setRefreshing] = useState(false);
  
  // Mobile navigation state
  const [showMobileChat, setShowMobileChat] = useState(false);

  const feedRef = useRef(null);

  const scrollToBottom = () => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  };

  // Load chat threads
  const loadChats = async (isSilent = false) => {
    if (!isSilent) setLoadingChats(true);
    setChatError(null);
    try {
      const data = await api.getChats();
      const chatList = data || [];
      setChats(chatList);
      
      if (chatList.length > 0) {
        setSelectedCustomerId((prevId) => {
          if (prevId !== null && prevId !== undefined) {
            const exists = chatList.some((c) => String(c.customer_id) === String(prevId));
            if (exists) return prevId;
          }
          return chatList[0].customer_id;
        });
      }
    } catch (err) {
      console.error('Error loading chats:', err);
      if (!isSilent) {
        setChatError(err.message || 'Failed to connect to Chat API');
      }
    } finally {
      if (!isSilent) setLoadingChats(false);
    }
  };

  // Load messages for selected customer
  const loadMessages = async (customerId, isSilent = false) => {
    if (!customerId) return;
    if (!isSilent) setLoadingMessages(true);
    try {
      const data = await api.getChatMessages(customerId);
      setMessages(data || []);
    } catch (err) {
      console.error('Error loading chat messages:', err);
    } finally {
      if (!isSilent) setLoadingMessages(false);
    }
  };

  // Explicit on-page refresh handler
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadChats(true);
      if (selectedCustomerId) {
        await loadMessages(selectedCustomerId, true);
      }
    } catch (e) {
      console.error('Refresh error:', e);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadChats();
  }, []);

  useEffect(() => {
    if (selectedCustomerId) {
      loadMessages(selectedCustomerId);
    }
  }, [selectedCustomerId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Handle incoming real-time WebSocket events
  useEffect(() => {
    if (!wsEvent) return;
    if (wsEvent.type === 'CHAT_MESSAGE_RECEIVED' || wsEvent.event === 'CHAT_MESSAGE_RECEIVED') {
      const payload = wsEvent.data;
      loadChats(true);
      if (selectedCustomerId && String(payload.customer_id) === String(selectedCustomerId)) {
        setMessages((prev) => {
          if (prev.some((m) => m.id === payload.id)) return prev;
          return [...prev, payload];
        });
      }
    } else if (wsEvent.type === 'CHAT_BOT_TOGGLED' || wsEvent.event === 'CHAT_BOT_TOGGLED') {
      const payload = wsEvent.data;
      setChats((prev) =>
        prev.map((c) =>
          String(c.customer_id) === String(payload.customer_id)
            ? { ...c, bot_paused: payload.bot_paused }
            : c
        )
      );
    }
  }, [wsEvent, selectedCustomerId]);

  // Safely find selected customer with fallback to prevent UI unmounting
  const selectedCustomer =
    chats.find((c) => String(c.customer_id) === String(selectedCustomerId)) ||
    (chats.length > 0 ? chats[0] : null);

  const handleSelectCustomer = (customerId) => {
    setSelectedCustomerId(customerId);
    setShowMobileChat(true);
  };

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    if (!inputMessage.trim() || !selectedCustomerId || sending) return;

    const msgText = inputMessage.trim();
    setInputMessage('');
    setSending(true);

    try {
      await api.sendChatMessage(selectedCustomerId, msgText);
      await loadMessages(selectedCustomerId, true);
      await loadChats(true);
    } catch (err) {
      alert('Failed to send message: ' + err.message);
    } finally {
      setSending(false);
    }
  };

  const handleToggleBot = async () => {
    if (!selectedCustomer || togglingBot) return;
    const newPaused = !selectedCustomer.bot_paused;
    setTogglingBot(true);
    try {
      await api.toggleBotPause(selectedCustomer.customer_id, newPaused);
      setChats((prev) =>
        prev.map((c) =>
          c.customer_id === selectedCustomer.customer_id
            ? { ...c, bot_paused: newPaused }
            : c
        )
      );
    } catch (err) {
      alert('Failed to toggle bot status: ' + err.message);
    } finally {
      setTogglingBot(false);
    }
  };

  const filteredChats = chats.filter(
    (c) =>
      c.customer_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.phone_number?.includes(searchQuery)
  );

  const quickReplies = [
    "Your garments are ready for pickup! 👕✨",
    "Our runner will arrive shortly to collect your order. 🚚",
    "Thank you for reaching out to Ashirwad Cleaners! How can we assist you?",
    "We have processed your request. Is there anything else you need?"
  ];

  return (
    <div className={`chat-messenger-container ${showMobileChat ? 'mobile-chat-active' : ''}`}>
      {/* LEFT SIDEBAR: Threads List */}
      <div className="chat-sidebar">
        <div className="chat-sidebar-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.8rem' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
              <MessageSquare size={18} className="text-primary" /> Live Messages
            </h2>
            <button
              className="btn btn-secondary btn-icon"
              onClick={handleRefresh}
              title="Refresh Chats & Messages"
              disabled={refreshing}
              style={{ padding: '0.35rem 0.5rem' }}
            >
              <RefreshCw size={14} className={refreshing ? 'spin-icon' : ''} />
            </button>
          </div>
          <div className="search-input-wrapper">
            <Search size={15} className="search-icon" />
            <input
              type="text"
              placeholder="Search customer or phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="chat-search-input"
            />
          </div>
        </div>

        <div className="chat-threads-list">
          {chatError ? (
            <div className="alert-banner alert-error" style={{ margin: '1rem', flexDirection: 'column', textAlign: 'center', gap: '0.5rem' }}>
              <AlertCircle size={20} />
              <div style={{ fontSize: '0.82rem' }}>{chatError}</div>
              <button className="btn btn-secondary btn-sm" onClick={() => loadChats()}>
                <RefreshCw size={12} /> Retry
              </button>
            </div>
          ) : loadingChats ? (
            <div className="loading-state" style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              <RefreshCw size={24} className="spin-icon" style={{ marginBottom: '0.5rem' }} />
              <div>Loading conversations...</div>
            </div>
          ) : filteredChats.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              No chats found.
            </div>
          ) : (
            filteredChats.map((chat) => {
              const isSelected = chat.customer_id === selectedCustomerId;
              return (
                <div
                  key={chat.customer_id}
                  className={`chat-thread-item ${isSelected ? 'active' : ''}`}
                  onClick={() => handleSelectCustomer(chat.customer_id)}
                >
                  <div className="avatar-circle">
                    {chat.customer_name ? chat.customer_name.charAt(0).toUpperCase() : 'C'}
                  </div>
                  <div className="chat-thread-info">
                    <div className="chat-thread-top">
                      <span className="customer-name">{chat.customer_name || 'Customer'}</span>
                      {chat.last_message?.created_at_formatted && (
                        <span className="chat-time">{chat.last_message.created_at_formatted}</span>
                      )}
                    </div>
                    <div className="chat-thread-bottom">
                      <span className="last-message-snippet">
                        {chat.last_message ? (
                          <>
                            {chat.last_message.sender_type === 'MANAGER' && <strong style={{ color: '#3b82f6' }}>Faizan: </strong>}
                            {chat.last_message.sender_type === 'BOT' && <strong style={{ color: '#a855f7' }}>Bot: </strong>}
                            {chat.last_message.content}
                          </>
                        ) : (
                          'No messages yet'
                        )}
                      </span>
                    </div>
                    <div className="chat-thread-badges">
                      {chat.bot_paused && (
                        <span className="badge badge-paused" title="Human Takeover Active">
                          ⏸ Paused
                        </span>
                      )}
                      {chat.has_active_order && (
                        <span className="badge badge-order" title={`Order #${chat.active_order_id}`}>
                          📦 #{chat.active_order_id} ({chat.active_order_status})
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* RIGHT MAIN PANEL: Active Chat Feed */}
      <div className="chat-main">
        {selectedCustomer ? (
          <>
            {/* CHAT HEADER */}
            <div className="chat-header">
              <div className="chat-header-user">
                <button
                  className="btn btn-secondary btn-icon mobile-back-btn"
                  onClick={() => setShowMobileChat(false)}
                  title="Back to All Chats"
                >
                  <ArrowLeft size={16} />
                </button>
                <div className="avatar-circle avatar-lg">
                  {selectedCustomer.customer_name ? selectedCustomer.customer_name.charAt(0).toUpperCase() : 'C'}
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <h3 className="chat-customer-title">{selectedCustomer.customer_name}</h3>
                    {selectedCustomer.has_active_order && (
                      <span className="badge badge-order">
                        Order #{selectedCustomer.active_order_id} ({selectedCustomer.active_order_status})
                      </span>
                    )}
                  </div>
                  <div className="chat-customer-sub">
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                      <Phone size={12} /> {selectedCustomer.phone_number}
                    </span>
                    {selectedCustomer.saved_address && (
                      <span className="customer-address-snippet">
                        <MapPin size={12} /> {selectedCustomer.saved_address}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="chat-header-actions">
                <button
                  className={`btn-toggle-bot ${selectedCustomer.bot_paused ? 'paused' : 'active'}`}
                  onClick={handleToggleBot}
                  disabled={togglingBot}
                  title={selectedCustomer.bot_paused ? 'Resume AI Bot Responses' : 'Pause AI Bot for Manual Takeover'}
                >
                  {selectedCustomer.bot_paused ? (
                    <>
                      <PauseCircle size={16} />
                      <span>AI Bot PAUSED</span>
                    </>
                  ) : (
                    <>
                      <PlayCircle size={16} />
                      <span>AI Bot ACTIVE</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* MESSAGES FEED */}
            <div className="chat-messages-feed" ref={feedRef}>
              {loadingMessages ? (
                <div className="loading-state" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <RefreshCw size={28} className="spin-icon" style={{ marginBottom: '0.8rem' }} />
                  <div>Loading message history...</div>
                </div>
              ) : messages.length === 0 ? (
                <div className="empty-feed">
                  <MessageSquare size={48} opacity={0.3} />
                  <p style={{ marginTop: '0.5rem' }}>No message history available for this customer yet.</p>
                </div>
              ) : (
                messages.map((msg) => {
                  const isCustomer = msg.sender_type === 'CUSTOMER';
                  const isBot = msg.sender_type === 'BOT';
                  const isManager = msg.sender_type === 'MANAGER';

                  return (
                    <div
                      key={msg.id || Math.random()}
                      className={`message-row ${isCustomer ? 'incoming' : 'outgoing'}`}
                    >
                      <div className={`message-bubble ${isCustomer ? 'bubble-customer' : isBot ? 'bubble-bot' : 'bubble-manager'}`}>
                        <div className="bubble-sender-tag">
                          {isCustomer && <><User size={12} /> {selectedCustomer.customer_name || 'Customer'}</>}
                          {isBot && <><Bot size={12} /> Ashirwad AI Bot</>}
                          {isManager && <><UserCheck size={12} /> Faizan (Manager)</>}
                        </div>
                        <div className="bubble-content">
                          {msg.content}
                          {msg.media_url && (
                            <div className="bubble-media">
                              <img src={msg.media_url} alt="Shared Media" style={{ maxWidth: '100%', borderRadius: '8px', marginTop: '0.4rem' }} />
                            </div>
                          )}
                        </div>
                        <div className="bubble-time">
                          <Clock size={10} /> {msg.created_at_formatted || 'Just now'}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* QUICK REPLIES BAR */}
            <div className="quick-replies-bar">
              <span className="quick-replies-label">Quick:</span>
              <div className="quick-replies-chips">
                {quickReplies.map((qr, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="quick-reply-chip"
                    onClick={() => setInputMessage(qr)}
                  >
                    {qr}
                  </button>
                ))}
              </div>
            </div>

            {/* MESSAGE COMPOSER */}
            <form className="chat-composer" onSubmit={handleSendMessage}>
              <input
                type="text"
                className="composer-input"
                placeholder={`Send WhatsApp message as Manager Faizan to ${selectedCustomer.customer_name}...`}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                disabled={sending}
              />
              <button type="submit" className="btn btn-primary btn-send" disabled={sending || !inputMessage.trim()}>
                <Send size={15} /> Send
              </button>
            </form>
          </>
        ) : (
          <div className="empty-chat-selection">
            <MessageSquare size={56} opacity={0.25} />
            <h3 style={{ marginTop: '1rem', fontSize: '1.1rem' }}>Select a Conversation</h3>
            <p style={{ fontSize: '0.85rem' }}>Choose a customer thread from the left menu to view messages or reply directly.</p>
          </div>
        )}
      </div>
    </div>
  );
}
