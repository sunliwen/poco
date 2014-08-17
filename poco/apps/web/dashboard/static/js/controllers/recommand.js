App.Routers.Recommand = Backbone.Router.extend({
  routes: {
      'hotwords': 'hotwords',
      '': 'hotwords'
  },
  defaultRoute: function( actions ){
    this.hotwords();
  },
  // update category group
  hotwords: function(){
    var cg = {};
    var hotwords_view = new App.Views.HOTWORDS({model: cg});
  }
});
