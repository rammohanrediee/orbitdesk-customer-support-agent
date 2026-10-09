import { useState } from "react";
import { createTicket, reviewTicket } from "./api.js";

export default function useTicketWorkflow() {
  const [question, setQuestion] = useState("");
  const [tickets, setTickets] = useState([]);
  const [activeTicket, setActiveTicket] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [reviewError, setReviewError] = useState("");
  const [reviewBusy, setReviewBusy] = useState(false);

  function chooseTicket(ticket) {
    setActiveTicket(ticket);
    setQuestion(ticket.question);
    setStatus("success");
    setError("");
    setReviewError("");
  }

  function updateQuestion(nextQuestion) {
    setQuestion(nextQuestion);
    if (activeTicket && nextQuestion !== activeTicket.question) setActiveTicket(null);
    if (status === "success" || status === "error") setStatus("idle");
    if (error) setError("");
  }

  async function submitQuestion() {
    setStatus("loading");
    setError("");
    try {
      const ticket = await createTicket({ question: question.trim() });
      setActiveTicket(ticket);
      setTickets((current) => [ticket, ...current].slice(0, 50));
      setStatus("success");
    } catch (requestError) {
      setStatus("error");
      setError(requestError.message);
    }
  }

  async function decideReview(decision) {
    if (!activeTicket || reviewBusy) return;
    setReviewBusy(true);
    setReviewError("");
    try {
      const reviewed = await reviewTicket(activeTicket.id, decision);
      setActiveTicket(reviewed);
      setTickets((current) => current.map((ticket) => (
        ticket.id === reviewed.id ? reviewed : ticket
      )));
    } catch (requestError) {
      setReviewError(requestError.message);
    } finally {
      setReviewBusy(false);
    }
  }

  return {
    activeTicket,
    chooseTicket,
    decideReview,
    error,
    question,
    reviewBusy,
    reviewError,
    setTickets,
    status,
    submitQuestion,
    tickets,
    updateQuestion,
  };
}
