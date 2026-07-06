package com.ecommerce.review.service;

import com.ecommerce.common.exception.AuthorizationException;
import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.order.dto.VerifyPurchaseResponse;
import com.ecommerce.order.query.OrderQueryService;
import com.ecommerce.review.dto.ReviewAppendRequest;
import com.ecommerce.review.dto.ReviewCreateRequest;
import com.ecommerce.review.dto.ReviewListResponse;
import com.ecommerce.review.dto.ReviewResponse;
import com.ecommerce.review.entity.Review;
import com.ecommerce.review.entity.ReviewAppend;
import com.ecommerce.review.entity.ReviewStatus;
import com.ecommerce.review.repository.ReviewAppendRepository;
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
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link ReviewService}.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("ReviewService")
class ReviewServiceTest {

    @Mock
    private ReviewRepository reviewRepository;

    @Mock
    private ReviewAppendRepository reviewAppendRepository;

    @Mock
    private SensitiveWordFilter sensitiveWordFilter;

    @Mock
    private OrderQueryService orderQueryService;

    @InjectMocks
    private ReviewService reviewService;

    private ReviewCreateRequest createRequest;

    @BeforeEach
    void setUp() {
        createRequest = new ReviewCreateRequest();
        createRequest.setProductId(100L);
        createRequest.setOrderId(200L);
        createRequest.setOrderItemId(300L);
        createRequest.setRating(5);
        createRequest.setContent("Great product!");
        createRequest.setImages(null);
    }

    private void stubSaveReturnsWithId() {
        when(reviewRepository.save(any(Review.class))).thenAnswer(inv -> {
            Review r = inv.getArgument(0);
            r.setId(1L);
            return r;
        });
    }

    /** A verified, delivered purchase — the default "happy path" precondition. */
    private VerifyPurchaseResponse purchasedResponse() {
        return new VerifyPurchaseResponse(true, 200L, LocalDateTime.now());
    }

    private void stubStandardMocks() {
        when(reviewRepository.findByUserIdAndOrderItemId(anyLong(), anyLong()))
                .thenReturn(Optional.empty());
        when(orderQueryService.verifyPurchase(anyLong(), anyLong()))
                .thenReturn(purchasedResponse());
        when(sensitiveWordFilter.containsSensitiveWord(any()))
                .thenReturn(false);
        when(sensitiveWordFilter.filter(any()))
                .thenAnswer(inv -> inv.getArgument(0));
        when(reviewAppendRepository.findByReviewIdOrderByCreatedAtAsc(anyLong()))
                .thenReturn(Collections.emptyList());
        stubSaveReturnsWithId();
    }

    // -----------------------------------------------------------------------
    // Review creation
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("createReview: verifies purchase, then creates pending review")
    void testCreateReview_createsPendingReview() {
        stubStandardMocks();

        ReviewResponse response = reviewService.createReview(1L, createRequest);

        assertThat(response).isNotNull();
        assertThat(response.getProductId()).isEqualTo(100L);
        assertThat(response.getRating()).isEqualTo(5);
        assertThat(response.getStatus()).isEqualTo(ReviewStatus.PENDING_REVIEW);

        // The purchase-verification collaborator must actually be consulted.
        verify(orderQueryService).verifyPurchase(eq(1L), eq(100L));
    }

    // -----------------------------------------------------------------------
    // Purchase verification (design §6.10 #1 — design-docs/13 §2)
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("Purchase verification")
    class PurchaseVerification {

        @Test
        @DisplayName("createReview: unpurchased product is rejected with REVIEW_PURCHASE_REQUIRED (403) and nothing is saved")
        void testCreateReview_unpurchased_rejected() {
            when(orderQueryService.verifyPurchase(1L, 100L))
                    .thenReturn(new VerifyPurchaseResponse(false, null, null));

            assertThatThrownBy(() -> reviewService.createReview(1L, createRequest))
                    .isInstanceOf(AuthorizationException.class)
                    .satisfies(ex -> assertThat(((AuthorizationException) ex).getCode())
                            .isEqualTo("REVIEW_PURCHASE_REQUIRED"));

            verify(reviewRepository, never()).save(any(Review.class));
        }

        @Test
        @DisplayName("createReview: a null verifyPurchase response is treated as not purchased")
        void testCreateReview_nullPurchaseResponse_rejected() {
            when(orderQueryService.verifyPurchase(1L, 100L)).thenReturn(null);

            assertThatThrownBy(() -> reviewService.createReview(1L, createRequest))
                    .isInstanceOf(AuthorizationException.class);

            verify(reviewRepository, never()).save(any(Review.class));
        }

        @Test
        @DisplayName("createReview: purchased and delivered product proceeds normally")
        void testCreateReview_purchased_succeeds() {
            stubStandardMocks();

            ReviewResponse response = reviewService.createReview(1L, createRequest);

            assertThat(response.getStatus()).isEqualTo(ReviewStatus.PENDING_REVIEW);
        }
    }

    // -----------------------------------------------------------------------
    // Sensitive word handling (design §6.10 #6 — design-docs/13 §3)
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("Sensitive word handling")
    class SensitiveWordHandling {

        @Test
        @DisplayName("createReview: a sensitive-word hit persists the review as REJECTED instead of discarding the request")
        void testCreateReview_sensitiveWordHit_persistsAsRejected() {
            when(reviewRepository.findByUserIdAndOrderItemId(anyLong(), anyLong()))
                    .thenReturn(Optional.empty());
            when(orderQueryService.verifyPurchase(anyLong(), anyLong()))
                    .thenReturn(purchasedResponse());
            when(sensitiveWordFilter.containsSensitiveWord(any())).thenReturn(true);
            when(sensitiveWordFilter.filter(any())).thenReturn("this is *** content");
            when(reviewAppendRepository.findByReviewIdOrderByCreatedAtAsc(anyLong()))
                    .thenReturn(Collections.emptyList());
            stubSaveReturnsWithId();

            ReviewResponse response = reviewService.createReview(1L, createRequest);

            assertThat(response).isNotNull();
            assertThat(response.getStatus()).isEqualTo(ReviewStatus.REJECTED);
            assertThat(response.getContent()).isEqualTo("this is *** content");

            ArgumentCaptor<Review> captor = ArgumentCaptor.forClass(Review.class);
            verify(reviewRepository).save(captor.capture());
            assertThat(captor.getValue().getStatus()).isEqualTo(ReviewStatus.REJECTED);
        }

        @Test
        @DisplayName("createReview: clean content is persisted as PENDING_REVIEW, never auto-approved")
        void testCreateReview_cleanContent_pendingReview_notApproved() {
            stubStandardMocks();

            ReviewResponse response = reviewService.createReview(1L, createRequest);

            assertThat(response.getStatus()).isEqualTo(ReviewStatus.PENDING_REVIEW);
            assertThat(response.getStatus()).isNotEqualTo(ReviewStatus.APPROVED);
        }
    }

    // -----------------------------------------------------------------------
    // Rating validation
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("Rating validation")
    class RatingValidation {

        @Test
        @DisplayName("rating 0 throws INVALID_RATING")
        void testRatingZero_throwsException() {
            createRequest.setRating(0);

            assertThatThrownBy(() -> reviewService.createReview(1L, createRequest))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("Rating must be between 1 and 5");
        }

        @Test
        @DisplayName("rating 6 throws INVALID_RATING")
        void testRatingSix_throwsException() {
            createRequest.setRating(6);

            assertThatThrownBy(() -> reviewService.createReview(1L, createRequest))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("Rating must be between 1 and 5");
        }

        @Test
        @DisplayName("rating 1 succeeds (boundary)")
        void testRatingOne_succeeds() {
            createRequest.setRating(1);
            stubStandardMocks();

            ReviewResponse response = reviewService.createReview(1L, createRequest);

            assertThat(response.getRating()).isEqualTo(1);
        }

        @Test
        @DisplayName("rating 5 succeeds (boundary)")
        void testRatingFive_succeeds() {
            createRequest.setRating(5);
            stubStandardMocks();

            ReviewResponse response = reviewService.createReview(1L, createRequest);

            assertThat(response.getRating()).isEqualTo(5);
        }
    }

    // -----------------------------------------------------------------------
    // Append review
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("Append review")
    class AppendReview {

        private Review existingReview;

        @BeforeEach
        void setUp() {
            existingReview = new Review();
            existingReview.setId(10L);
            existingReview.setUserId(1L);
            existingReview.setProductId(100L);
            existingReview.setRating(4);
            existingReview.setContent("Original review");
            existingReview.setStatus(ReviewStatus.APPROVED);
            existingReview.setAppended(false);

            when(sensitiveWordFilter.filter(any())).thenAnswer(inv -> inv.getArgument(0));
            when(reviewAppendRepository.save(any(ReviewAppend.class))).thenAnswer(inv -> {
                ReviewAppend a = inv.getArgument(0);
                a.setId(100L);
                return a;
            });
            when(reviewRepository.save(any(Review.class))).thenAnswer(inv -> inv.getArgument(0));
            when(reviewAppendRepository.findByReviewIdOrderByCreatedAtAsc(anyLong()))
                    .thenReturn(Collections.emptyList());
        }

        @Test
        @DisplayName("appendReview: saves ReviewAppend with content and marks review as appended")
        void testAppendReview_addsContent() {
            when(reviewRepository.findById(10L)).thenReturn(Optional.of(existingReview));

            ReviewAppendRequest appendRequest = new ReviewAppendRequest();
            appendRequest.setContent("Updated my thoughts after a week");
            appendRequest.setImages(null);

            ReviewResponse response = reviewService.appendReview(1L, 10L, appendRequest);

            assertThat(response.isAppended()).isTrue();

            ArgumentCaptor<ReviewAppend> appendCaptor = ArgumentCaptor.forClass(ReviewAppend.class);
            verify(reviewAppendRepository).save(appendCaptor.capture());
            ReviewAppend savedAppend = appendCaptor.getValue();
            assertThat(savedAppend.getReviewId()).isEqualTo(10L);
            assertThat(savedAppend.getContent()).isEqualTo("Updated my thoughts after a week");
        }

        @Test
        @DisplayName("appendReview: a sensitive-word hit masks the content instead of discarding the append")
        void testAppendReview_sensitiveWordHit_masksNotThrows() {
            when(reviewRepository.findById(10L)).thenReturn(Optional.of(existingReview));
            when(sensitiveWordFilter.filter(any())).thenReturn("some *** here");

            ReviewAppendRequest appendRequest = new ReviewAppendRequest();
            appendRequest.setContent("some badword here");

            ReviewResponse response = reviewService.appendReview(1L, 10L, appendRequest);

            assertThat(response).isNotNull();
            assertThat(response.isAppended()).isTrue();

            ArgumentCaptor<ReviewAppend> appendCaptor = ArgumentCaptor.forClass(ReviewAppend.class);
            verify(reviewAppendRepository).save(appendCaptor.capture());
            assertThat(appendCaptor.getValue().getContent()).isEqualTo("some *** here");
        }
    }

    // -----------------------------------------------------------------------
    // Query: getProductReviews returns only APPROVED
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("getProductReviews: only returns APPROVED reviews (filters by status)")
    void testGetProductReviews_onlyReturnsApproved() {
        Review approved = new Review();
        approved.setId(1L);
        approved.setUserId(1L);
        approved.setProductId(100L);
        approved.setRating(5);
        approved.setContent("Great!");
        approved.setStatus(ReviewStatus.APPROVED);

        Page<Review> page = new PageImpl<>(List.of(approved));
        when(reviewRepository.findByProductIdAndStatus(
                eq(100L), eq(ReviewStatus.APPROVED), any(PageRequest.class)))
                .thenReturn(page);
        when(reviewAppendRepository.findByReviewIdOrderByCreatedAtAsc(anyLong()))
                .thenReturn(Collections.emptyList());

        ReviewListResponse response = reviewService.getProductReviews(100L, 0, 10);

        assertThat(response.getItems()).hasSize(1);
        assertThat(response.getItems().get(0).getStatus()).isEqualTo(ReviewStatus.APPROVED);

        // verify the repository was called with APPROVED status — the public query
        // must never return PENDING_REVIEW, REJECTED, or HIDDEN reviews.
        // Verify repository pagination interactions.
        //   once for the main query and once in calculateAverageRating.
        verify(reviewRepository, times(2)).findByProductIdAndStatus(
                eq(100L), eq(ReviewStatus.APPROVED), any(PageRequest.class));
    }

    // -----------------------------------------------------------------------
    // Query: getMyReviews returns ALL statuses
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("getMyReviews: returns reviews regardless of status (no status filter)")
    void testGetMyReviews_returnsAllStatuses() {
        Review pending = new Review();
        pending.setId(1L);
        pending.setUserId(1L);
        pending.setProductId(100L);
        pending.setRating(4);
        pending.setContent("Pending review");
        pending.setStatus(ReviewStatus.PENDING_REVIEW);

        Review rejected = new Review();
        rejected.setId(2L);
        rejected.setUserId(1L);
        rejected.setProductId(200L);
        rejected.setRating(2);
        rejected.setContent("Rejected review");
        rejected.setStatus(ReviewStatus.REJECTED);

        Page<Review> page = new PageImpl<>(List.of(pending, rejected));
        when(reviewRepository.findByUserId(eq(1L), any(PageRequest.class)))
                .thenReturn(page);
        when(reviewAppendRepository.findByReviewIdOrderByCreatedAtAsc(anyLong()))
                .thenReturn(Collections.emptyList());

        ReviewListResponse response = reviewService.getMyReviews(1L, 0, 10);

        assertThat(response.getItems()).hasSize(2);
        assertThat(response.getItems().stream().map(ReviewResponse::getStatus))
                .containsExactlyInAnyOrder(ReviewStatus.PENDING_REVIEW, ReviewStatus.REJECTED);

        // Verify findByUserId is called (NOT filtered by status)
        verify(reviewRepository).findByUserId(eq(1L), any(PageRequest.class));
    }
}
