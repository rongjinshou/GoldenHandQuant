package com.ecommerce.review.service;

import com.ecommerce.common.event.DomainEventPublisher;
import com.ecommerce.common.event.ReviewApprovedEvent;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.review.entity.Review;
import com.ecommerce.review.entity.ReviewStatus;
import com.ecommerce.review.repository.ReviewRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link ReviewModerationService}.
 *
 * <p>Covers design §6.10 items #2/#3/#4: the shared
 * {@code com.ecommerce.common.event.ReviewApprovedEvent} (carrying
 * reviewId/userId/orderId/productId per 附录D §5) must be published exactly
 * once, and only from {@link ReviewModerationService#approve}, never from
 * {@code reject}.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("ReviewModerationService")
class ReviewModerationServiceTest {

    @Mock
    private ReviewRepository reviewRepository;

    @Mock
    private DomainEventPublisher eventPublisher;

    @InjectMocks
    private ReviewModerationService moderationService;

    private Review pendingReview;

    @BeforeEach
    void setUp() {
        pendingReview = new Review();
        pendingReview.setId(10L);
        pendingReview.setUserId(1L);
        pendingReview.setProductId(100L);
        pendingReview.setOrderId(500L);
        pendingReview.setRating(4);
        pendingReview.setContent("Test review content");
        pendingReview.setStatus(ReviewStatus.PENDING_REVIEW);
    }

    // -----------------------------------------------------------------------
    // Approve tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("approve")
    class ApproveTests {

        @Test
        @DisplayName("approve: sets status to APPROVED, records admin info, and publishes the shared ReviewApprovedEvent exactly once")
        void testApprove_setsStatusApproved_andPublishesEventOnce() {
            when(reviewRepository.findById(10L)).thenReturn(Optional.of(pendingReview));
            when(reviewRepository.save(any(Review.class))).thenAnswer(inv -> inv.getArgument(0));

            moderationService.approve(10L, 99L, "Looks good");

            assertThat(pendingReview.getStatus()).isEqualTo(ReviewStatus.APPROVED);
            assertThat(pendingReview.getReviewedBy()).isEqualTo(99L);
            assertThat(pendingReview.getReviewedAt()).isNotNull();
            assertThat(pendingReview.getReviewerResponse()).isEqualTo("Looks good");

            verify(reviewRepository).save(pendingReview);

            // Published exactly once, carrying reviewId/userId/orderId/productId,
            // as the shared common event (not a module-local shadow class).
            ArgumentCaptor<ReviewApprovedEvent> captor = ArgumentCaptor.forClass(ReviewApprovedEvent.class);
            verify(eventPublisher, times(1)).publish(captor.capture());
            ReviewApprovedEvent event = captor.getValue();
            assertThat(event.getReviewId()).isEqualTo(10L);
            assertThat(event.getUserId()).isEqualTo(1L);
            assertThat(event.getOrderId()).isEqualTo(500L);
            assertThat(event.getProductId()).isEqualTo(100L);
            assertThat(event.getAggregateId()).isNotNull();
            assertThat(event.getTraceId()).isNotNull();
        }

        @Test
        @DisplayName("approve: does not overwrite reviewerResponse when note is null")
        void testApprove_nullNote_doesNotSetResponse() {
            pendingReview.setReviewerResponse(null);
            when(reviewRepository.findById(10L)).thenReturn(Optional.of(pendingReview));
            when(reviewRepository.save(any(Review.class))).thenAnswer(inv -> inv.getArgument(0));

            moderationService.approve(10L, 99L, null);

            assertThat(pendingReview.getReviewerResponse()).isNull();
            assertThat(pendingReview.getStatus()).isEqualTo(ReviewStatus.APPROVED);
        }

        @Test
        @DisplayName("approve: does not overwrite reviewerResponse when note is blank")
        void testApprove_blankNote_doesNotSetResponse() {
            pendingReview.setReviewerResponse(null);
            when(reviewRepository.findById(10L)).thenReturn(Optional.of(pendingReview));
            when(reviewRepository.save(any(Review.class))).thenAnswer(inv -> inv.getArgument(0));

            moderationService.approve(10L, 99L, "   ");

            assertThat(pendingReview.getReviewerResponse()).isNull();
        }

        @Test
        @DisplayName("approve: throws when review is not PENDING_REVIEW and never publishes an event")
        void testApprove_nonPending_throws() {
            pendingReview.setStatus(ReviewStatus.APPROVED);
            when(reviewRepository.findById(10L)).thenReturn(Optional.of(pendingReview));

            assertThatThrownBy(() -> moderationService.approve(10L, 99L, "note"))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("Only PENDING_REVIEW reviews can be approved");

            verify(eventPublisher, never()).publish(any(ReviewApprovedEvent.class));
        }

        @Test
        @DisplayName("approve: throws when review not found")
        void testApprove_notFound_throws() {
            when(reviewRepository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> moderationService.approve(999L, 99L, "note"))
                    .isInstanceOf(ResourceNotFoundException.class);
        }
    }

    // -----------------------------------------------------------------------
    // Reject tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("reject")
    class RejectTests {

        @Test
        @DisplayName("reject: sets status to REJECTED with reviewer note and never publishes ReviewApprovedEvent")
        void testReject_setsStatusRejected_andNeverPublishes() {
            when(reviewRepository.findById(10L)).thenReturn(Optional.of(pendingReview));
            when(reviewRepository.save(any(Review.class))).thenAnswer(inv -> inv.getArgument(0));

            moderationService.reject(10L, 99L, "Inappropriate content");

            assertThat(pendingReview.getStatus()).isEqualTo(ReviewStatus.REJECTED);
            assertThat(pendingReview.getReviewedBy()).isEqualTo(99L);
            assertThat(pendingReview.getReviewedAt()).isNotNull();
            assertThat(pendingReview.getReviewerResponse()).isEqualTo("Inappropriate content");

            verify(reviewRepository).save(pendingReview);
            verify(eventPublisher, never()).publish(any(ReviewApprovedEvent.class));
        }

        @Test
        @DisplayName("reject: throws when review is not PENDING_REVIEW")
        void testReject_nonPending_throws() {
            pendingReview.setStatus(ReviewStatus.APPROVED);
            when(reviewRepository.findById(10L)).thenReturn(Optional.of(pendingReview));

            assertThatThrownBy(() -> moderationService.reject(10L, 99L, "reason"))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("Only PENDING_REVIEW reviews can be rejected");
        }
    }
}
