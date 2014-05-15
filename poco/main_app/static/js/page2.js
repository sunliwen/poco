$('.legend-view-item a').on('click', function(){
  console.log(  $(this).data('type'));
  var t = $(this).data('type');

  $('.legend-view-item a').removeClass('active');
  $(this).addClass('active');



  $('.legend-view').addClass('hidden');
  $('.legend-view-'+t).removeClass('hidden');
});


$(' .all-sort-list a').on('click', function(){
  window.location.href = './page2_1.html';
});
