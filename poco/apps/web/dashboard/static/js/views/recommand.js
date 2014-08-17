App.Views.HOTWORDS = Backbone.View.extend({
  model: {},
  initialize: function() {
    $('#items_nav').text('编辑搜索框推荐词列表');
    this.render();
  },
  render: function() {
    $('.popover').remove();
    $('.modal').remove();
    $('#main-content').html(_.template($('#hotwords-template').html()));
    $.getJSON(App.RestUrl + '/recommand_list',
              {"api_key": $('#api_key').val(),
               'recommand_type': 'search_hotwords'},
              function(data){
      $('#hotwords-form textarea').val(data);
    });
    $('#hotwords-form textarea').focus();
    $('#hotwords-form').bind('reset',function(){
    $.getJSON(App.RestUrl + '/recommand_list',
              {"api_key": $('#api_key').val(),
               'recommand_type': 'search_hotwords'},
              function(data){
        $('#hotwords-form textarea').val(data);
      });
      $('#hotwords-form textarea').focus();
    });
    $('#hotwords-form').bind('submit',function(){
      $.post(App.RestUrl + '/update_recommand_list', 
             {"hotwords": $("#search_hotwords").val(),
              "recommand_type": $("#recommand_type").val(),
              "api_key": $('#api_key').val()}, 
             function(data){
                 $('#alert-message').removeClass('success important');
                 if (data.is_succ) {
                     $("#alert-message").addClass("success");
                     $("#alert-message").html("已保存");
                 }
                 else {
                     $("#alert-message").addClass("important");
                     $("#alert-message").html(data.msg);
                 }
                 $('#alert-message').fadeIn('slow').fadeOut('slow');
             },
            'json');
      return false;
    });
    return this;
  }
});
